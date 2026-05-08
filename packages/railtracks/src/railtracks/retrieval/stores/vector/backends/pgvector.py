from __future__ import annotations

import json


_NOT_INITIALIZED = (
    "call await PgvectorBackend.initialize() first and ensure asyncpg and pgvector are installed"
)


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
    payload JSONB). Filters are applied as JSONB text equality. Similarity
    is cosine: score = 1 - cosine_distance.

    Call initialize() before any other method.

    Args:
        dsn:   asyncpg connection string.
        table: Table name (created if absent).
        dim:   Vector dimension. When given the column is typed vector(dim),
               which enables index creation. Omit to use an untyped vector
               column (fine for development, no ANN index support).
    """

    def __init__(
        self,
        dsn: str,
        *,
        table: str = "memory_entries",
        dim: int | None = None,
    ) -> None:
        self._dsn = dsn
        self._table = table
        self._dim = dim
        self._pool = None

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
                    id      TEXT PRIMARY KEY,
                    embedding {vec_type},
                    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb
                )
                """
            )

    async def upsert(self, id: str, vector: list[float], payload: dict) -> None:
        if self._pool is None:
            raise RuntimeError(_NOT_INITIALIZED)
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
        if self._pool is None:
            raise RuntimeError(_NOT_INITIALIZED)

        where, params = _build_where(filters, start_index=2)
        sql = f"""
            SELECT id,
                   1 - (embedding <=> $1::vector) AS score,
                   payload
            FROM   "{self._table}"
            {where}
            ORDER  BY embedding <=> $1::vector
            LIMIT  {top_k}
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, vector, *params)

        return [
            (row["id"], float(row["score"]), _decode_payload(row["payload"]))
            for row in rows
        ]

    async def delete(self, id: str) -> None:
        if self._pool is None:
            raise RuntimeError(_NOT_INITIALIZED)
        async with self._pool.acquire() as conn:
            await conn.execute(
                f'DELETE FROM "{self._table}" WHERE id = $1', id
            )

    async def delete_where(self, filters: dict) -> None:
        if self._pool is None:
            raise RuntimeError(_NOT_INITIALIZED)
        if not filters:
            return
        where, params = _build_where(filters, start_index=1)
        async with self._pool.acquire() as conn:
            await conn.execute(
                f'DELETE FROM "{self._table}" {where}', *params
            )