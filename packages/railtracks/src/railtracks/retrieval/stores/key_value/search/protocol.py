from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SearchAlgorithm(Protocol):
    """Ranks a ``{key: value}`` snapshot against a free-text query.

    A deliberately separate contract from
    :class:`~railtracks.retrieval.stores.key_value.protocol.KeyValueStore`:
    the store stays a plain exact-match dict, and ranking is layered on top
    rather than baked in. Callers (e.g. ``KeyValueMemoryToolSet``) depend on
    this protocol rather than a concrete algorithm, so the ranking strategy
    can be swapped — or tuned via a config object — without touching the
    store or the caller.
    """

    def search(
        self, items: dict[str, str], query: str, *, top_k: int = 5
    ) -> list[tuple[str, str, float]]:
        """Return up to ``top_k`` ``(key, value, score)`` triples, best first.

        Args:
            items: The ``{key: value}`` snapshot to search, e.g. the result
                of ``KeyValueStore.items()``.
            query: The free-text search string.
            top_k: Maximum number of results to return.

        Returns:
            Up to ``top_k`` results sorted by descending score. Empty when
            nothing matches or the query is blank.
        """
        ...
