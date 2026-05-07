from __future__ import annotations


class PgvectorBackend:
    """PostgreSQL + pgvector backend (stub).

    Full implementation is deferred. Only ``initialize()`` is wired to
    validate the optional-dependency import path.
    """

    def __init__(self, dsn: str, table: str = "memory_entries") -> None:
        self._dsn = dsn
        self._table = table

    async def initialize(self) -> None:
        try:
            import asyncpg  # noqa: F401
        except ImportError:
            raise ImportError(
                "asyncpg is required for PgvectorBackend. "
                "Install it with: pip install railtracks[stores-vector]"
            ) from None

    async def upsert(self, id: str, vector: list[float], payload: dict) -> None:
        raise NotImplementedError(
            "call await PgvectorBackend.initialize() first and ensure asyncpg is installed"
        )

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]:
        raise NotImplementedError(
            "call await PgvectorBackend.initialize() first and ensure asyncpg is installed"
        )

    async def delete(self, id: str) -> None:
        raise NotImplementedError(
            "call await PgvectorBackend.initialize() first and ensure asyncpg is installed"
        )

    async def delete_where(self, filters: dict) -> None:
        raise NotImplementedError(
            "call await PgvectorBackend.initialize() first and ensure asyncpg is installed"
        )
