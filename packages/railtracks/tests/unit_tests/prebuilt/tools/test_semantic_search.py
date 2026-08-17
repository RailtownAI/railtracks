"""Tests for prebuilt/tools/memory/search — SemanticSearch.

Uses a deterministic stub embedder (bag-of-words over a fixed vocabulary) so
ranking and the incremental-index bookkeeping can be asserted without a live
embedding provider. The stub also counts how many texts it embeds, which is how
the "only re-embed the delta" behaviour is verified.
"""

from __future__ import annotations

import re

from railtracks.retrieval.embedding.base import Embedding
from railtracks.retrieval.embedding.models import EmbeddingMetrics, TextEmbeddings
from railtracks.retrieval.stores.vector.backends import InMemoryBackend
from railtracks.prebuilt.tools.memory.search import SearchAlgorithm, SemanticSearch

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A closed vocabulary spanning every token used in the fixtures below. Mapping
# each token to a fixed dimension makes the embedding deterministic and
# collision-free, so cosine similarity is an exact function of shared tokens.
_VOCAB = [
    "fruit", "apples", "and", "oranges",
    "language", "python", "programming",
    "city", "vancouver", "canada", "toronto",
]
_IDX = {tok: i for i, tok in enumerate(_VOCAB)}


class StubEmbedder(Embedding):
    """Deterministic bag-of-words embedder that counts what it embeds."""

    default_batch_size = 16

    def __init__(self) -> None:
        self.embed_calls = 0
        self.texts_embedded = 0

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        self.embed_calls += 1
        self.texts_embedded += len(texts)
        vectors = []
        for text in texts:
            vec = [0.0] * len(_VOCAB)
            for tok in _TOKEN_RE.findall(text.lower()):
                if tok in _IDX:
                    vec[_IDX[tok]] += 1.0
            vectors.append(vec)
        return TextEmbeddings(
            vectors=vectors,
            metrics=EmbeddingMetrics(model="stub", dimension=len(_VOCAB)),
        )


ITEMS = {
    "fruit": "apples and oranges",
    "language": "python programming",
    "city": "vancouver canada",
}


def _fresh() -> tuple[StubEmbedder, SemanticSearch]:
    embedder = StubEmbedder()
    return embedder, SemanticSearch(embedding=embedder)


# ---------------------------------------------------------------------------
# Protocol conformance & edge cases
# ---------------------------------------------------------------------------


def test_satisfies_search_algorithm_protocol():
    assert isinstance(SemanticSearch(StubEmbedder()), SearchAlgorithm)


async def test_blank_query_returns_empty_without_embedding():
    embedder, search = _fresh()
    assert await search.search(ITEMS, "   ") == []
    assert embedder.embed_calls == 0


async def test_empty_items_returns_empty_without_embedding():
    embedder, search = _fresh()
    assert await search.search({}, "apples") == []
    assert embedder.embed_calls == 0


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


async def test_ranks_semantically_closest_entry_first():
    _embedder, search = _fresh()
    assert (await search.search(ITEMS, "apples"))[0][0] == "fruit"
    assert (await search.search(ITEMS, "programming"))[0][0] == "language"
    assert (await search.search(ITEMS, "vancouver"))[0][0] == "city"


async def test_returns_key_value_score_triples():
    _embedder, search = _fresh()
    key, value, score = (await search.search(ITEMS, "apples"))[0]
    assert key == "fruit"
    assert value == "apples and oranges"
    assert isinstance(score, float)


async def test_top_k_limits_results():
    items = {f"k{i}": "apples" for i in range(6)}
    _embedder, search = _fresh()
    hits = await search.search(items, "apples", top_k=2)
    assert len(hits) == 2


# ---------------------------------------------------------------------------
# Incremental index: only the delta is (re-)embedded
# ---------------------------------------------------------------------------


async def test_unchanged_corpus_embeds_only_the_query():
    embedder, search = _fresh()
    await search.search(ITEMS, "apples")  # 3 corpus entries + 1 query
    assert embedder.texts_embedded == len(ITEMS) + 1

    before = embedder.texts_embedded
    await search.search(ITEMS, "python")
    assert embedder.texts_embedded - before == 1  # query only, no re-embed


async def test_changed_value_reembeds_only_that_entry():
    embedder, search = _fresh()
    items = dict(ITEMS)
    await search.search(items, "apples")

    before = embedder.texts_embedded
    items["city"] = "toronto"
    await search.search(items, "apples")
    assert embedder.texts_embedded - before == 2  # 1 changed entry + query


async def test_removed_key_is_dropped_from_results():
    _embedder, search = _fresh()
    items = dict(ITEMS)
    await search.search(items, "apples")

    del items["fruit"]
    hits = await search.search(items, "apples")
    assert "fruit" not in {key for key, _v, _s in hits}


async def test_emptying_store_prunes_the_index():
    embedder, search = _fresh()
    await search.search(ITEMS, "apples")

    before = embedder.embed_calls
    # Store emptied: sync runs (prunes vectors) but the query is not embedded.
    assert await search.search({}, "apples") == []
    assert embedder.embed_calls == before


# ---------------------------------------------------------------------------
# Persistence: a restart reuses embeddings via the backend snapshot
# ---------------------------------------------------------------------------


async def test_persisted_backend_reused_across_instances(tmp_path):
    snap = str(tmp_path / "vectors.json")

    emb1 = StubEmbedder()
    await SemanticSearch(emb1, InMemoryBackend(snapshot_path=snap)).search(
        ITEMS, "apples"
    )
    assert emb1.texts_embedded == len(ITEMS) + 1

    # Fresh instance, same snapshot: corpus already indexed -> query only.
    emb2 = StubEmbedder()
    hits = await SemanticSearch(emb2, InMemoryBackend(snapshot_path=snap)).search(
        ITEMS, "programming"
    )
    assert emb2.texts_embedded == 1
    assert hits[0][0] == "language"


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_lazy_export_from_memory_package():
    from railtracks.prebuilt.tools.memory import SemanticSearch as Exported

    assert Exported is SemanticSearch
