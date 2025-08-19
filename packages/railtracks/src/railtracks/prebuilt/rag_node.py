from typing import Type
import railtracks as rt
from railtracks.nodes.concrete import DynamicFunctionNode
from railtracks.rag.rag_core import RAG, SearchResult


def rag_node(
    documents: list,
    input_type: str = "text",  # 'text' or 'path'
    embed_model="text-embedding-3-small",
    token_count_model="gpt-4o",
    chunk_size=1000,
    chunk_overlap=200,
) -> Type[DynamicFunctionNode]:
    """
    Creates a rag node that allows you to vector the search the provided documents.

    Args:
        documents (list): List of documents to process. Can be raw text, file paths, or TextObject instances.
        embed_model (str): Model name for embedding service.
        token_count_model (str): Model name for token counting.
        chunk_size (int): Size of each text chunk.
        chunk_overlap (int): Overlap between chunks.

    Returns:
        callable of type DynamicFunctionNode: A node to be invoked upon request.

    """

    rag_core = RAG(
        docs=documents,
        embed_config={
            "model": embed_model,
        },
        store_config={},
        chunk_config={
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "model": token_count_model,
        },
        input_type=input_type,
    )
    rag_core.embed_all()

    def query(query: str, top_k: int = 1) -> SearchResult:
        result = rag_core.search(query, top_k=top_k)
        return result

    return rt.function_node(query)
