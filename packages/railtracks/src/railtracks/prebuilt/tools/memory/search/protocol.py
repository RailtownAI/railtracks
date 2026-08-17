from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SearchAlgorithm(Protocol):
    """Ranks a ``{key: value}`` snapshot against a free-text query.

    Callers (e.g. ``KeyValueMemoryToolSet``) depend on
    this protocol rather than a concrete algorithm, so the ranking strategy
    can be swapped — lexical, semantic, hybrid — without touching the store
    or the caller.
    """

    async def search(
        self, items: dict[str, str], query: str, *, top_k: int = 5
    ) -> list[tuple[str, str, float]]:
        """Return up to ``top_k`` ``(key, value, score)`` triples, best first.

        Args:
            items: The ``{key: value}`` snapshot to search, e.g. the result
                of ``KeyValueStore.items()``. Ranking over a passed-in snapshot
                (rather than a store handle) keeps the algorithm decoupled from
                any concrete store; a stateful ranker uses it to keep its own
                index in sync with the store it does not own.
            query: The free-text search string.
            top_k: Maximum number of results to return.

        Returns:
            Up to ``top_k`` results sorted by descending score. Empty when
            nothing matches or the query is blank.
        """
        ...
