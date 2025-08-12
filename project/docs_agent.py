from railtracks.llm import MessageHistory
from railtracks.rag.embedding_service import EmbeddingService
from railtracks.rag.vector_store import InMemoryVectorStore


def query_embedding_store(
    query: str,
    vector_store: InMemoryVectorStore,
    top_k: int = 5
) -> List[SearchResult]:
    """
    Query the embedding store for similar documents.

    Args:
        query: The query string to search for.
        vector_store: The InMemoryVectorStore instance to query.
        top_k: Number of top results to return.

    Returns:
        A list of SearchResult objects containing the most similar documents.
    """
    return vector_store.search(query, top_k=top_k)

async def hook_function(message_history: MessageHistory) -> MessageHistory:
    """
    Hook function to inject memory into the user prompt.

    This function asks the memory agent for relevant details and injects it
    into the latest user message.
    """
    # Get the latest user message
    user_message = message_history[-1] if message_history else None

    # If no user message, return as is
    if not user_message:
        return message_history

    embedder = EmbeddingService()
    query_vector = embedder.embed([user_message])[0]  # embed returns List[List[float]]

    results = vector_store.search(query_vector, top_k=5, embed=False)

    # Inject the memory context into the user message
    if memory_context:
        message_history[-1] = UserMessage(
            content=(
                user_message.content + f"\n\nRelevant Memory Context:\n{memory_context}"
            )
        )

    return message_history

