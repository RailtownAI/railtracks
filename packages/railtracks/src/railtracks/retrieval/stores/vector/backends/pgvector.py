from __future__ import annotations

import json

from typing_extensions import Self

from ..metric import DistanceMetric

_NOT_INITIALIZED = (
    "PgvectorBackend is not initialized — "
    "call await PgvectorBackend.create(...) or await backend.initialize() first"
)

_PG_OPERATOR = {
    DistanceMetric.COSINE: "<=>",
    DistanceMetric.L2: "<->",
    DistanceMetric.IP: "<#>",
}


def _pg_to_score(metric: DistanceMetric, distance: float) -> float:
    """Convert a raw pgvector distance to a similarity score (higher = better).

    pgvector operator conventions:
        <=>  cosine distance (1 - cos_sim)   → score = 1 - d
        <->  L2 distance (||a-b||)           → score = 1 / (1 + d)
        <#>  negative inner product (-⟨a,b⟩) → score = -d  (= dot_product)
    """
    if metric is DistanceMetric.COSINE:
        return 1.0 - distance
    if metric is DistanceMetric.L2:
        return 1.0 / (1.0 + distance)
    return -distance  # IP


def _build_where(filters: dict, start_index: int = 1) -> tuple[str, list]:
    """Build a parameterized WHERE clause from a flat equality dict.

    Payload fields are accessed as JSONB text: payload->>'key' = $N.
    start_index controls the first $N used, allowing callers to offset
    around other positional params (e.g. $1 = query vector in search).
    """
    if not filters:
        return "", []
    conditions = [
        f"payload->>'{k}' = ${start_index + i}" for i, k in enumerate(filters)
    ]
    params = [str(v) for v in filters.values()]
    return "WHERE " + " AND ".join(conditions), params


def _decode_payload(raw) -> dict:
    return raw if isinstance(raw, dict) else json.loads(raw)


class PgvectorBackend:
    """PostgreSQL + pgvector VectorBackend.

    Stores vectors in a single table with columns (id TEXT, embedding vector,
    payload JSONB). Filters are applied as JSONB text equality.

    Call initialize() before any other method.

    Args:
        dsn:    asyncpg connection string.
        table:  Table name (created if absent).
        dim:    Vector dimension. When given the column is typed vector(dim),
                which enables ANN index creation. Omit for development use.
        metric: Distance metric used for similarity search. Defaults to COSINE.
    """

    def __init__(
        self,
        dsn: str,
        *,
        table: str = "memory_entries",
        dim: int | None = None,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> None:
        self._dsn = dsn
        self._table = table
        self._dim = dim
        self._metric = metric
        self._pool = None

    def _require_initialized(self) -> None:
        if self._pool is None:
            raise RuntimeError(_NOT_INITIALIZED)

    @classmethod
    async def create(
        cls,
        dsn: str,
        *,
        table: str = "memory_entries",
        dim: int | None = None,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> Self:
        """Create and initialize a PgvectorBackend in one step."""
        backend = cls(dsn, table=table, dim=dim, metric=metric)
        await backend.initialize()
        return backend

    async def initialize(self) -> None:
        try:
            import asyncpg
            from pgvector.asyncpg import register_vector
        except ImportError:
            raise ImportError(
                "asyncpg and pgvector are required for PgvectorBackend. "
                "Install them with: pip install railtracks[stores-vector]"
            ) from None

        async def _init_conn(conn) -> None:
            await register_vector(conn)

        self._pool = await asyncpg.create_pool(self._dsn, init=_init_conn)

        vec_type = f"vector({self._dim})" if self._dim else "vector"
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS "{self._table}" (
                    id        TEXT PRIMARY KEY,
                    embedding {vec_type},
                    payload   JSONB NOT NULL DEFAULT '{{}}'::jsonb
                )
                """
            )

    async def upsert(self, id: str, vector: list[float], payload: dict) -> None:
        self._require_initialized()
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO "{self._table}" (id, embedding, payload)
                VALUES ($1, $2, $3::jsonb)
                ON CONFLICT (id) DO UPDATE
                    SET embedding = EXCLUDED.embedding,
                        payload   = EXCLUDED.payload
                """,
                id,
                vector,
                json.dumps(payload),
            )

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]:
        self._require_initialized()

        op = _PG_OPERATOR[self._metric]
        where, params = _build_where(filters, start_index=2)
        sql = f"""
            SELECT id,
                   embedding {op} $1::vector AS distance,
                   payload
            FROM   "{self._table}"
            {where}
            ORDER  BY embedding {op} $1::vector
            LIMIT  {top_k}
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, vector, *params)

        return [
            (
                row["id"],
                _pg_to_score(self._metric, float(row["distance"])),
                _decode_payload(row["payload"]),
            )
            for row in rows
        ]

    async def delete(self, id: str) -> None:
        self._require_initialized()
        async with self._pool.acquire() as conn:
            await conn.execute(f'DELETE FROM "{self._table}" WHERE id = $1', id)

    async def delete_where(self, filters: dict) -> None:
        self._require_initialized()
        if not filters:
            return
        where, params = _build_where(filters, start_index=1)
        async with self._pool.acquire() as conn:
            await conn.execute(f'DELETE FROM "{self._table}" {where}', *params)
