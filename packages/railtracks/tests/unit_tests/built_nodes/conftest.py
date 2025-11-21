import pytest

from typing import Callable, Any, Optional

from railtracks.vector_stores.vector_store_base import (
    Chunk,
    VectorStore,
    OneOrMany,
)


class MockVectorStore(VectorStore):
    """
    A concrete in-memory mock of VectorStore for testing and development.

    You can optionally pass in custom functions to override behavior of any
    method (upsert, search, fetch, delete, count). If not provided, default
    in-memory behavior is used.

    Example:
        store = MockVectorStore(
            collection_name="test",
            embedding_function=lambda x: [[0.0]],
            search_func=lambda query, top_k, **_: [...]
        )
    """

    def __init__(
        self,
        collection_name: str = "mock",
        embedding_function: Callable[[list[str]], list[list[float]]] = lambda x: [[0.0] for _ in x],
        *,
        upsert_func: Optional[Callable] = None,
        search_func: Optional[Callable] = None,
        fetch_func: Optional[Callable] = None,
        delete_func: Optional[Callable] = None,
        count_func: Optional[Callable] = None,
    ):
        super().__init__(collection_name, embedding_function)

        # Optional user-provided overrides
        self._custom_upsert = upsert_func
        self._custom_search = search_func
        self._custom_fetch = fetch_func
        self._custom_delete = delete_func
        self._custom_count = count_func


    # -----------------------------
    # Utility helpers
    # -----------------------------
    def _ensure_list(self, x: OneOrMany[Any]) -> list[Any]:
        return x if isinstance(x, list) else [x]


    def _make_chunk(self, value: Chunk | str):
        if isinstance(value, Chunk):
            return value
        return Chunk(content=value)

    # -----------------------------
    # VectorStore interface
    # -----------------------------
    def upsert(
        self,
        content: OneOrMany[Chunk] | OneOrMany[str],
    ):
        """Insert or update vectors into the mock store."""
        if self._custom_upsert:
            return self._custom_upsert(content)

        raise NotImplementedError()



    def fetch(self, ids: OneOrMany[str]):
        """Fetch chunks from the mock store by id."""
        if self._custom_fetch:
            return self._custom_fetch(ids)

        raise NotImplementedError()
    

    def search(
        self,
        query: OneOrMany[Chunk] | OneOrMany[str],
        top_k: int = 10,
        where: Optional[dict[str, Any]] = None,
        include: Optional[list[str]] = None,
    ):
        """
        Very dumb default: returns the *first top_k items* in the store,
        ignoring the actual query. Intended for tests unless overridden.
        """
        if self._custom_search:
            return self._custom_search(query, top_k, where=where, include=include)

        raise NotImplementedError()

    def delete(self, ids: OneOrMany[str], where: Optional[dict[str, Any]] = None):
        """Deletes items by id. Ignores metadata unless overridden."""
        if self._custom_delete:
            return self._custom_delete(ids, where)

        raise NotImplementedError()

    def count(self) -> int:
        """Returns number of stored vectors."""
        if self._custom_count:
            return self._custom_count()
        
        raise NotImplementedError()

@pytest.fixture
def mock_vector_store():
    return MockVectorStore()
