"""
Main script for running the RAG-enhanced Project Assistant

This script demonstrates how to use the RAG-enhanced memory context and agent
to create an intelligent project assistant that automatically retrieves relevant
context based on user queries.
"""

import asyncio

import railtracks as rt
from agents import (
    code_execution_agent,
    file_system_agent,
    memory_agent,
    note_taking_agent,
    web_search_agent,
)
from rag_memory import RAGMemoryContext, initialize_rag_session


# Create a RAG-enhanced main agent
def create_rag_enhanced_main_agent(top_k=3):
    """
    Create a RAG-enhanced main agent with access to all specialized agents.

    Args:
        top_k: Number of relevant context items to include

    Returns:
        A RAG-enhanced main agent
    """
    # Create the tool nodes for the specialized agents
    tool_nodes = {
        rt.function_node(
            lambda query, agent="memory": asyncio.run(
                rt.call(memory_agent, instructions=query)
            )
        ),
        rt.function_node(
            lambda query, agent="web_search": asyncio.run(
                rt.call(web_search_agent, instructions=query)
            )
        ),
        rt.function_node(
            lambda query, agent="note_taking": asyncio.run(
                rt.call(note_taking_agent, instructions=query)
            )
        ),
        rt.function_node(
            lambda query, agent="code_execution": asyncio.run(
                rt.call(code_execution_agent, instructions=query)
            )
        ),
        rt.function_node(
            lambda query, agent="file_system": asyncio.run(
                rt.call(file_system_agent, instructions=query)
            )
        ),
    }

    # Create the RAG-enhanced main agent
    rag_main_agent = rt.chatui_node(
        pretty_name="RAG-Enhanced Project Assistant",
        tool_nodes=tool_nodes,
        system_message="""You are an intelligent project assistant with advanced project-specific knowledge.
        You have access to a memory system that stores project knowledge, and various tools to help with tasks.
        
        You are equipped with a RAG (Retrieval-Augmented Generation) system that automatically retrieves
        relevant context from your memory based on the user's query. This allows you to provide more
        accurate and helpful responses by leveraging your stored knowledge.
        
        Available specialized agents:
        - Memory Agent: For storing and retrieving project knowledge
        - Web Search Agent: For searching the web for information
        - Note-Taking Agent: For creating and managing notes
        - Code Execution Agent: For executing Python code
        - File System Agent: For interacting with the file system
        
        When you start, first check the memory to understand what you already know about the project.
        Always be helpful, informative, and focused on the user's needs.
        
        When you receive a query, relevant context from your memory will be automatically added to the prompt.
        Use this context to inform your response, but don't repeat it verbatim unless necessary.""",
        llm_model="claude-3-5-sonnet-20240620",
    )

    # Override the invoke method to add relevant context
    original_invoke = rag_main_agent.invoke

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
    rag_main_agent.invoke = rag_enhanced_invoke

    return rag_main_agent


# Main function to run the RAG-enhanced agent
async def run_rag_agent(
    embed_model="text-embedding-3-small",
    token_count_model="gpt-4o",
    chunk_size=1000,
    chunk_overlap=200,
    top_k=3,
):
    """
    Run the RAG-enhanced agent.

    Args:
        embed_model: Model to use for embeddings
        token_count_model: Model to use for token counting
        chunk_size: Size of each chunk in tokens
        chunk_overlap: Overlap between chunks in tokens
        top_k: Number of relevant context items to include
    """
    # Initialize a session with the RAG memory context
    with initialize_rag_session(
        embed_model=embed_model,
        token_count_model=token_count_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    ) as session:
        # Create the RAG-enhanced main agent
        rag_main_agent = create_rag_enhanced_main_agent(top_k=top_k)

        # Start the chat UI
        await rt.call(rag_main_agent)


if __name__ == "__main__":
    # Run the RAG-enhanced agent
    asyncio.run(run_rag_agent())
