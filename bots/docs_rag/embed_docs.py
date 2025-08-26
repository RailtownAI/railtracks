import os
from pathlib import Path

from railtracks.rag.chunking_service import TextChunkingService
from railtracks.rag.embedding_service import EmbeddingService
from railtracks.rag.vector_store import InMemoryVectorStore
from railtracks.rag.vector_store.base import VectorRecord

from bots.docs_rag.extract_snippets import extract_snippets


# === Embedding service (simplified based on your litellm wrapper) ===
def embed_and_index_docs(
    base_dir: str | Path,
    normal_chunk_size: int = 1000,
    normal_chunk_overlap: int = 160,
    api_chunk_size: int = 500,
    api_chunk_overlap: int = 80,
):
    base_dir = Path(base_dir)
    embedder = EmbeddingService()

    stores = {
        "main": InMemoryVectorStore(embedding_service=embedder, normalize=True),
        "advanced": InMemoryVectorStore(embedding_service=embedder, normalize=True),
        "api": InMemoryVectorStore(embedding_service=embedder, normalize=True),
    }

    normal_chunker = TextChunkingService(
        chunk_size=normal_chunk_size,
        chunk_overlap=normal_chunk_overlap,
        strategy=TextChunkingService.chunk_by_token,
    )
    api_chunker = TextChunkingService(
        chunk_size=api_chunk_size,
        chunk_overlap=api_chunk_overlap,
        strategy=TextChunkingService.chunk_by_token,
    )

    for root, dirs, files in os.walk(base_dir):
        root_path = Path(root)

        if "api_reference" in root_path.parts:
            store_key, chunker = "api", api_chunker
        elif "advanced_usage" in root_path.parts:
            store_key, chunker = "advanced", normal_chunker
        else:
            store_key, chunker = "main", normal_chunker

        for fname in files:
            if fname.endswith(".md"):
                rel_path = Path(root_path / fname).relative_to(base_dir)
                rel_path_str = str(rel_path).replace("\\", "/")

                print(
                    f"Processing file: {rel_path_str} in {root_path} of type {store_key}"
                )
                text = Path(root_path / fname).read_text(encoding="utf-8")
                workspace_root = str(base_dir.parent)
                text = extract_snippets(text, workspace_root)

                chunks = chunker.chunk(text)
                vecs = embedder.embed(chunks)
                records = [
                    VectorRecord(
                        id=f"{store_key}-{rel_path_str}-{i}",
                        vector=vecs[i],
                        text=chunks[i],
                        metadata={"source_file": rel_path_str, "chunk_index": i},
                    )
                    for i in range(len(chunks))
                ]
                stores[store_key].add(records, embed=False)

    return stores


if __name__ == "__main__":
    docs_dir = "../../docs"

    print("Indexing documents...")
    stores = embed_and_index_docs(docs_dir)
    print("Indexed.")

    stores["main"].persist("docs_vector_store.pkl")
    stores["advanced"].persist("docs_advanced_vector_store.pkl")
    stores["api"].persist("docs_api_vector_store.pkl")
