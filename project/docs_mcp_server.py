from typing import List

from project.custom_chat_ui import custom_chatui_node
import railtracks as rt
from railtracks.llm import MessageHistory, UserMessage, OpenAILLM
from railtracks.rag.embedding_service import EmbeddingService
from railtracks.rag.vector_store import InMemoryVectorStore

vector_store = InMemoryVectorStore.load("docs_vector_store.pkl")

def query_railtracks_docs(
    query: str,
    top_k: int = 5
) -> List[str]:
    """
    Query the documentation of the RailTracks framework for relevent information.

    Args:
        query: The query string to search for.
        top_k: Number of top results to return.

    Returns:
        A list of strings containing the most relevant documentation chunks.
    """
    embedder = EmbeddingService()
    query_vector = embedder.embed([query])[0]
    results = vector_store.search(query_vector, top_k=top_k)
    return [
        f"Result {i + 1} Source: {res.record.metadata['source_file']} chunk #{res.record.metadata['chunk_index']}\n"
        f"Text snippet:\n{res.record.text}"
        for i, res in enumerate(results)
    ]
