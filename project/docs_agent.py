from typing import List

from project.custom_chat_ui import custom_chatui_node
import railtracks as rt
from railtracks.llm import MessageHistory, UserMessage, OpenAILLM
from railtracks.rag.embedding_service import EmbeddingService
from railtracks.rag.vector_store import InMemoryVectorStore

vector_store = InMemoryVectorStore.load("docs_vector_store.pkl")

def query_embedding_store(
    query: str,
    top_k: int = 5
) -> List[str]:
    """
    Query the embedding store for similar documents.

    Args:
        query: The query string to search for.
        top_k: Number of top results to return.

    Returns:
        A list of SearchResult objects containing the most similar documents.
    """
    embedder = EmbeddingService()
    query_vector = embedder.embed([query])[0]
    results = vector_store.search(query_vector, top_k=top_k)
    return [
        f"Result {i + 1} Source: {res.record.metadata['source_file']} chunk #{res.record.metadata['chunk_index']}\n"
        f"Text snippet:\n{res.record.text}"
        for i, res in enumerate(results)
    ]


async def hook_function(message_history: MessageHistory) -> MessageHistory:
    """
    Hook function to inject memory into the user prompt.

    This function asks the memory agent for relevant details and injects it
    into the latest user message.
    """
    print("Hook function called with message history")
    # Get the latest user message
    user_message = message_history[-1] if message_history else None
    if not isinstance(user_message, UserMessage):
        return message_history

    # If no user message, return as is
    if not user_message:
        return message_history

    results = query_embedding_store(user_message.content, top_k=5)

    # Inject the memory context into the user message
    message_history[-1] = UserMessage(
        content=(
            user_message.content + f"\n\nRelevant Memory Context:\n{'\n\n'.join(results)}"
        )
    )

    return message_history

docs_agent = custom_chatui_node(
    pretty_name="RAG-Enhanced Project Assistant",
    tool_nodes=[rt.function_node(query_embedding_store)] ,
    system_message="""You are a RailTracks project assistant with advanced knowledge of this codebase.
    
    You have access to a memory system that stores RailTracks-specific documentation, code, and development practices, as well as tools to help with project tasks.
    
    Relevant context from your memory will be automatically provided based on the user's query. The memory system contains a project overview, code snippets, and development instructions that can be searched if you need to recall anything.
    
    This allows you to provide more accurate and helpful responses by leveraging RailTracks-specific knowledge.
    
    When needed, first check the memory to understand what is already known about RailTracks. Always be helpful, informative, and focused on the user's needs.
    
    When you receive a query, relevant context from your memory will be automatically added to the prompt. Use this context to inform your response, but do not repeat it verbatim unless necessary.""",
    llm_model=OpenAILLM(model_name="gpt-4o"),
    user_function_hook=hook_function,
)

with rt.Session(logging_setting="VERBOSE", timeout=1000000000):
    rt.call_sync(docs_agent, rt.llm.MessageHistory([]))

