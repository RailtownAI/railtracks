from __future__ import annotations

import hashlib

from railtracks.retrieval.embedding.base import Embedding
from railtracks.retrieval.stores.vector.backends import InMemoryBackend
from railtracks.retrieval.stores.vector.base import VectorBackend

# The backend has no "list all" primitive; list_where breaks at this limit.
# An agent's memory holds tens to low hundreds of entries, so a ceiling this
# high is effectively "everything" while staying an explicit bound.
_INDEX_SCAN_LIMIT = 1_000_000


def _content(key: str, value: str) -> str:
    """The text embedded for one entry.

    Key and value are folded into a single string so the key's wording
    contributes to the entry's meaning. (Field-level weighting — biasing
    toward key matches the way :class:`~.lexical.LexicalSearch` does — would
    need dual vectors; a single combined vector is the deliberate v1 choice.)
    """
    return f"{key}: {value}"


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SemanticSearch:
    """Dense-vector ranking over key-value pairs. Satisfies ``SearchAlgorithm``.

    Composes two reusable pieces of the retrieval stack — an
    :class:`~railtracks.retrieval.embedding.base.Embedding` to turn text into
    vectors and a :class:`~railtracks.retrieval.stores.vector.base.VectorBackend`
    for the similarity math and persistence — without touching the heavier
    ``VectorStore``/``StoreEntry`` document model. This is the *only* place in
    the search layer that depends on the vector package, keeping the coupling
    to a single file.

    The vector index is maintained lazily. Each :meth:`search` call diffs the
    passed-in ``items`` snapshot against what is already indexed (by a content
    fingerprint stored in each payload) and embeds only new or changed
    entries, dropping removed keys. So the store's contents drive the index —
    the ranker never has to own the store — and re-embedding cost is paid only
    on the delta, not on every query.

    Give the ranker a backend constructed with a ``snapshot_path`` to persist
    embeddings across process restarts::

        from railtracks.retrieval.stores.vector.backends import InMemoryBackend

        search = SemanticSearch(
            embedding=my_embedder,
            backend=InMemoryBackend(snapshot_path="memory_vectors.json"),
        )

    Keep that path distinct from the key-value store's own snapshot — vectors
    are large and belong beside the index, not the facts.

    Args:
        embedding: Embedder used for both the corpus and the query. The same
            embedder must be used across calls (the index stores its vectors).
        backend: Vector backend holding the embeddings, keyed by the
            key-value key. Defaults to a fresh, in-process
            :class:`InMemoryBackend` (cosine similarity, no persistence).
    """

    def __init__(
        self, embedding: Embedding, backend: VectorBackend | None = None
    ) -> None:
        self._embedding = embedding
        self._backend = backend if backend is not None else InMemoryBackend()

    async def _sync_index(self, items: dict[str, str]) -> None:
        """Bring the vector index in line with ``items``, embedding only the delta."""
        indexed = {
            key: payload.get("fingerprint")
            for key, payload in await self._backend.list_where({}, _INDEX_SCAN_LIMIT)
        }

        texts = {key: _content(key, value) for key, value in items.items()}
        fingerprints = {key: _fingerprint(text) for key, text in texts.items()}

        stale = [key for key in indexed if key not in items]
        changed = [key for key in items if indexed.get(key) != fingerprints[key]]

        for key in stale:
            await self._backend.delete(key)

        if changed:
            vectors = (await self._embedding.aembed([texts[k] for k in changed])).vectors
            for key, vector in zip(changed, vectors):
                await self._backend.upsert(
                    key,
                    vector,
                    {"value": items[key], "fingerprint": fingerprints[key]},
                )

    async def search(
        self, items: dict[str, str], query: str, *, top_k: int = 5
    ) -> list[tuple[str, str, float]]:
        if not query.strip():
            return []

        # Sync first — even for an empty snapshot — so emptying the store prunes
        # its vectors from the index rather than leaving them orphaned. Only
        # then short-circuit: with nothing indexed there is nothing to match,
        # so skip the pointless query embedding.
        await self._sync_index(items)
        if not items:
            return []

        query_vector = (await self._embedding.aembed([query])).vectors[0]
        hits = await self._backend.search(query_vector, top_k, {})
        return [(key, payload["value"], score) for key, score, payload in hits]
