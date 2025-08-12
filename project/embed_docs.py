import os
from pathlib import Path

from railtracks.rag.chunking_service import TextChunkingService
from railtracks.rag.embedding_service import EmbeddingService
from railtracks.rag.vector_store import InMemoryVectorStore
from railtracks.rag.vector_store.base import VectorRecord


# === Embedding service (simplified based on your litellm wrapper) ===
def embed_and_index_docs(
    base_dir: str | Path,
    api_reference_subdir: str = "api_reference",
    normal_chunk_size: int = 1000,
    normal_chunk_overlap: int = 160,
    api_chunk_size: int = 500,
    api_chunk_overlap: int = 80,
) -> InMemoryVectorStore:
    base_dir = Path(base_dir)
    embedder = EmbeddingService()
    store = InMemoryVectorStore(embedding_service=embedder, normalize=True)

    normal_chunker = TextChunkingService(
        chunk_size=normal_chunk_size, chunk_overlap=normal_chunk_overlap, strategy=TextChunkingService.chunk_by_token
    )
    api_chunker = TextChunkingService(
        chunk_size=api_chunk_size, chunk_overlap=api_chunk_overlap, strategy=TextChunkingService.chunk_by_token
    )

    all_texts = []
    all_metadatas = []

    for root, dirs, files in os.walk(base_dir):
        root_path = Path(root)
        print(f"Processing directory: {root_path}")
        is_api_ref = api_reference_subdir in root_path.parts

        chunker = api_chunker if is_api_ref else normal_chunker

        for fname in files:
            if not fname.endswith((".md", ".txt")):
                continue
            file_path = root_path / fname
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            chunks = chunker.chunk(content)

            for i, chunk in enumerate(chunks):
                metadata = {
                    "source_file": str(file_path.relative_to(base_dir)),
                    "chunk_index": i,
                    "is_api_reference": is_api_ref,
                }
                all_texts.append(chunk)
                all_metadatas.append(metadata)

    vecs = embedder.embed(all_texts)
    records = [
        VectorRecord(id=f"chunk-{i}", vector=vecs[i], text=all_texts[i], metadata=all_metadatas[i])
        for i in range(len(all_texts))
    ]
    store.add(records, embed=False)

    return store


if __name__ == "__main__":
    docs_dir = "../docs"

    print("Indexing documents...")
    vector_store = embed_and_index_docs(docs_dir)
    print("Indexed.")

    # Example query
    query = "How to use a function as a tool?"
    print(f"\nSearch results for query: {query}\n")

    embedder = EmbeddingService()
    query_vector = embedder.embed([query])[0]  # embed returns List[List[float]]

    results = vector_store.search(query_vector, top_k=5, embed=False)

    for i, res in enumerate(results):
        print(f"Result {i+1} [score={res.score:.3f}]:")
        print(f"Source: {res.record.metadata['source_file']} chunk #{res.record.metadata['chunk_index']}")
        print(f"Text snippet:\n{res.record.text[:400]}...\n")