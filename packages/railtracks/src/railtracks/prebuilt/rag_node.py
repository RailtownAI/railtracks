import railtracks as rt

from ..rag.rag_core import RAG


def rag_node(
    documents: list,
    embed_model="text-embedding-3-small",
    token_count_model="gpt-4o",
    chunk_size=1000,
    chunk_overlap=200,
):
    """
    Creates a rag node that allows you to vector the search the provided documents.

    Args:

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
    )
    rag_core.embed_all()

    def query(query: str) -> list:
        result = rag_core.search(query, top_k=2)
        return result

    return rt.function_node(query)
