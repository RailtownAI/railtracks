"""Quick nfcorpus backend comparison using deterministic hashed text vectors.

Install ``datasets`` in addition to ``railtracks[stores-turbovec]`` before
running this script. This microbenchmark compares store mechanics, not semantic
retrieval quality; it reports result overlap with the uncompressed baseline.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time

from datasets import load_dataset
from railtracks.retrieval.stores.vector.backends.in_memory import InMemoryBackend
from railtracks.retrieval.stores.vector.backends.turbovec import TurbovecBackend

_DIMENSION = 768
_TOKEN = re.compile(r"\w+", re.UNICODE)


def hashed_vector(text: str) -> list[float]:
    values = [0.0] * _DIMENSION
    for token in _TOKEN.findall(text.casefold()):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        slot = int.from_bytes(digest[:4], "little") % _DIMENSION
        values[slot] += 1.0 if digest[4] & 1 else -1.0
    norm = sum(value * value for value in values) ** 0.5
    return [value / norm for value in values] if norm else values


async def main() -> None:
    corpus = load_dataset("BeIR/nfcorpus", "corpus", split="corpus[:1000]")
    queries = load_dataset("BeIR/nfcorpus", "queries", split="queries[:100]")
    texts = [str(row.get("title", "")) + " " + str(row["text"]) for row in corpus]
    vectors = [hashed_vector(text) for text in texts]
    query_vectors = [hashed_vector(row["text"]) for row in queries]

    baseline_results: list[list[str]] = []
    turbovec_results: list[list[str]] = []
    for name, backend in (
        ("in-memory", InMemoryBackend()),
        ("turbovec", TurbovecBackend()),
    ):
        started = time.perf_counter()
        for i, vector in enumerate(vectors):
            await backend.upsert(str(corpus[i]["_id"]), vector, {"split": "nfcorpus"})
        ingest_seconds = time.perf_counter() - started
        started = time.perf_counter()
        results = []
        for vector in query_vectors:
            results.append(await backend.search(vector, 10, {"split": "nfcorpus"}))
        search_seconds = time.perf_counter() - started
        ids = [[item[0] for item in result] for result in results]
        if name == "in-memory":
            baseline_results = ids
        else:
            turbovec_results = ids
        print(
            f"{name}: vectors={len(vectors)} queries={len(query_vectors)} "
            f"ingest={ingest_seconds:.3f}s search={search_seconds:.3f}s "
            f"mean_query={search_seconds / len(query_vectors) * 1000:.3f}ms"
        )
    overlap = sum(
        len(set(expected) & set(actual)) / 10
        for expected, actual in zip(baseline_results, turbovec_results)
    ) / len(query_vectors)
    print(f"Turbovec mean top-10 overlap vs InMemoryBackend: {overlap:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
