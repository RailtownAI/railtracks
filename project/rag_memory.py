"""
RAG-enhanced Memory Context for Project Assistant

This module extends the PersistentMemoryContext with RAG capabilities to automatically
retrieve relevant context based on user queries.
"""

from typing import Any, Dict, List

import railtracks as rt
from memory_agent import MEMORY_FILE_PATH, PersistentMemoryContext
from railtracks.rag.rag_core import RAG
from railtracks.rag.vector_store.base import SearchResult


class RAGMemoryContext(PersistentMemoryContext):
    """
    A context that persists memory to a file between sessions and provides RAG capabilities
    to automatically retrieve relevant context based on user queries.
    """

    def __init__(
        self,
        file_path: str = MEMORY_FILE_PATH,
        embed_model: str = "text-embedding-3-small",
        token_count_model: str = "gpt-4o",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """
        Initialize the RAG memory context.

        Args:
            file_path: Path to the memory file
            embed_model: Model to use for embeddings
            token_count_model: Model to use for token counting
            chunk_size: Size of each chunk in tokens
            chunk_overlap: Overlap between chunks in tokens
        """
        super().__init__(file_path)

        # Initialize RAG system
        self.embed_model = embed_model
        self.token_count_model = token_count_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Create RAG system with initial documents
        self._initialize_rag()

    def _initialize_rag(self):
        """Initialize the RAG system with documents from memory."""
        # Convert memory entries to documents
        documents = self._memory_to_documents()

        # Create RAG system
        self.rag = RAG(
            docs=documents,
            embed_config={
                "model": self.embed_model,
            },
            store_config={},
            chunk_config={
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "model": self.token_count_model,
            },
            input_type="text",
        )

        # Embed all documents
        self.rag.embed_all()

    def _memory_to_documents(self) -> List[str]:
        """
        Convert memory entries to documents for RAG.

        Returns:
            List of document strings
        """
        documents = []

        # Process each category
        categories = ["facts", "concepts", "code_snippets", "resources", "notes"]
        for category in categories:
            category_dict = self.get(category, {})

            for key, entry in category_dict.items():
                # Create a formatted document with metadata
                doc = f"CATEGORY: {category}\n"
                doc += f"KEY: {key}\n"
                doc += f"TAGS: {', '.join(entry['tags'])}\n"
                doc += f"IMPORTANCE: {entry['importance']}\n"
                doc += f"CONTENT:\n{entry['content']}\n"

                documents.append(doc)

        return documents

    def update(self, data: Dict[str, Any]) -> None:
        """Update memory and save to file, then update RAG system."""
        super().update(data)
        self._reinitialize_rag()

    def put(self, key: str, value: Any):
        """Put value in memory and save to file, then update RAG system."""
        super().put(key, value)
        self._reinitialize_rag()

    def delete(self, key: str):
        """Delete key from memory and save to file, then update RAG system."""
        super().delete(key)
        self._reinitialize_rag()

    def _reinitialize_rag(self):
        """Reinitialize the RAG system after memory changes."""
        self._initialize_rag()

    def search_relevant_context(self, query: str, top_k: int = 3) -> List[SearchResult]:
        """
        Search for relevant context based on a query.

        Args:
            query: The search query
            top_k: Number of results to return

        Returns:
            List of search results
        """
        return self.rag.search(query, top_k=top_k)

    def get_context_for_prompt(self, query: str, top_k: int = 3) -> str:
        """
        Get formatted context for a prompt based on a query.

        Args:
            query: The search query
            top_k: Number of results to return

        Returns:
            Formatted context string
        """
        results = self.search_relevant_context(query, top_k=top_k)

        if not results:
            return ""

        context = "RELEVANT CONTEXT:\n\n"

        for i, result in enumerate(results):
            context += f"--- Context {i + 1} ---\n"
            context += result.record.text + "\n\n"

        return context


# Function to create a RAG-enhanced session
def initialize_rag_session(
    embed_model: str = "text-embedding-3-small",
    token_count_model: str = "gpt-4o",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
):
    """
    Initialize a session with the RAG memory context.

    Args:
        embed_model: Model to use for embeddings
        token_count_model: Model to use for token counting
        chunk_size: Size of each chunk in tokens
        chunk_overlap: Overlap between chunks in tokens

    Returns:
        A session with the RAG memory context
    """
    # Create RAG memory context
    memory_context = RAGMemoryContext(
        embed_model=embed_model,
        token_count_model=token_count_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    # Register the memory context
    rt.set_config(save_state=True)

    # Return a session with the memory context
    return rt.Session()


# Create a RAG-enhanced chatui_node that automatically adds relevant context to prompts
def rag_enhanced_chatui_node(
    tool_nodes,
    *,
    port: int = None,
    host: str = None,
    auto_open: bool = True,
    pretty_name: str = None,
    llm_model=None,
    max_tool_calls: int = None,
    system_message=None,
    top_k: int = 3,
):
    """
    Create a RAG-enhanced chatui_node that automatically adds relevant context to prompts.

    Args:
        tool_nodes: Set of tool nodes
        port: Port for the chat UI
        host: Host for the chat UI
        auto_open: Whether to automatically open the chat UI
        pretty_name: Pretty name for the node
        llm_model: LLM model to use
        max_tool_calls: Maximum number of tool calls
        system_message: System message for the node
        top_k: Number of relevant context items to include

    Returns:
        A RAG-enhanced chatui_node
    """
    # Create the base chatui_node
    base_node = rt.chatui_node(
        tool_nodes=tool_nodes,
        port=port,
        host=host,
        auto_open=auto_open,
        pretty_name=pretty_name,
        llm_model=llm_model,
        max_tool_calls=max_tool_calls,
        system_message=system_message,
    )

    # Override the invoke method to add relevant context
    original_invoke = base_node.invoke

    async def rag_enhanced_invoke(self, *args, **kwargs):
        """
        Enhanced invoke method that adds relevant context to the prompt.
        """
        # Get the user message
        user_message = kwargs.get("instructions", "")

        if user_message:
            # Get the RAG memory context
            memory_context = rt.context._context_var_store.get()

            if isinstance(memory_context, RAGMemoryContext):
                # Get relevant context
                context = memory_context.get_context_for_prompt(
                    user_message, top_k=top_k
                )

                # Add context to the prompt
                if context:
                    enhanced_message = f"{context}\n\nUSER QUERY: {user_message}"
                    kwargs["instructions"] = enhanced_message

        # Call the original invoke method
        return await original_invoke(self, *args, **kwargs)

    # Replace the invoke method
    base_node.invoke = rag_enhanced_invoke

    return base_node


# Main function to run the RAG-enhanced agent
async def run_rag_agent():
    """Run the RAG-enhanced agent."""
    with initialize_rag_session() as session:
        # Import the main agent from agents.py
        from agents import main_agent

        # Start the chat UI
        await rt.call(main_agent)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_rag_agent())
