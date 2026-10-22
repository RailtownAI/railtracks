"""Small, opt-in nfcorpus comparison for the in-memory and Turbovec stores.

Install ``datasets`` and ``sentence-transformers`` in addition to
``railtracks[stores-turbovec]`` before running this script.
"""

from __future__ import annotations

import asyncio
import time

from datasets import load_dataset
from railtracks.retrieval.stores.vector.backends.in_memory import InMemoryBackend
from railtracks.retrieval.stores.vector.backends.turbovec import TurbovecBackend
from sentence_transformers import SentenceTransformer


async def main() -> None:
    corpus = load_dataset("BeIR/nfcorpus", "corpus", split="corpus[:1000]")
    queries = load_dataset("BeIR/nfcorpus", "queries", split="queries[:100]")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    texts = [str(row.get("title", "")) + " " + str(row["text"]) for row in corpus]
    vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    query_vectors = model.encode(
        [row["text"] for row in queries],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    for name, backend in (
        ("in-memory", InMemoryBackend()),
        ("turbovec", TurbovecBackend()),
    ):
        started = time.perf_counter()
        for i, vector in enumerate(vectors):
            await backend.upsert(
                str(corpus[i]["_id"]), vector.tolist(), {"split": "nfcorpus"}
            )
        ingest_seconds = time.perf_counter() - started
        started = time.perf_counter()
        for vector in query_vectors:
            await backend.search(vector.tolist(), 10, {"split": "nfcorpus"})
        search_seconds = time.perf_counter() - started
        print(
            f"{name}: vectors={len(vectors)} queries={len(query_vectors)} ingest={ingest_seconds:.3f}s search={search_seconds:.3f}s"
        )


if __name__ == "__main__":
    asyncio.run(main())
