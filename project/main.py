"""
Main script for running the RAG-enhanced Project Assistant

This script demonstrates how to use the RAG-enhanced memory context and agent
to create an intelligent project assistant that automatically retrieves relevant
context based on user queries.
"""

import railtracks as rt
from memory_agent import memory, memory_agent_node, memory_agent
from railtracks.llm import MessageHistory, UserMessage
from railtracks.llm.models.api_providers import OpenAILLM

from examples.integrations.sandbox_python_integration import (
    create_sandbox_container,
    execute_code,
    kill_sandbox,
)
from examples.integrations.webseach_integration import fetch_mcp_tools, google_search


def hook_function(message_history: MessageHistory) -> MessageHistory:
    """
    Hook function to inject memory into the user prompt.

    This function asks the memory agent for relevant details and injects it
    into the latest user message.
    """
    # Get the latest user message
    user_message = message_history[-1] if message_history else None

    return MessageHistory([UserMessage("Tell me what 1+1 is?")])

    # If no user message, return as is
    if not user_message:
        return message_history

    # Ask the memory agent for relevant context
    request = (
        f"If applicable, find relevant context for: {user_message.content}"
        f"Otherwise, return an empty string."
    )
    memory_context = rt.call_sync(memory_agent, request=request).result
    print(f"Memory context retrieved: {memory_context}")

    # Inject the memory context into the user message
    if memory_context:
        message_history[-1] = UserMessage(
            content=user_message.content
            + f"\n\nRelevant Memory Context:\n{memory_context}"
            + "\n<hehehe>\n"
        )

    return message_history


tool_nodes = [memory_agent_node, google_search, execute_code] + fetch_mcp_tools

model = OpenAILLM(model_name="gpt-4o")
model.add_pre_hook(hook_function)

# Create the RAG-enhanced main agent
rag_main_agent = rt.chatui_node(
    pretty_name="RAG-Enhanced Project Assistant",
    tool_nodes=tool_nodes,
    system_message="""You are an intelligent project assistant with advanced project-specific knowledge.
    You have access to a memory system that stores project knowledge, and various tools to help with tasks.

    Relevant context from your memory will be automatically provided based on the user's query. 
    The memory system contains a project overview and various memory entries that can be searched.
    
    This allows you to provide more accurate and helpful responses by leveraging your stored knowledge.
    You should be frequently updating your memory with new information you learn about the project. Anything that is relevant to the fundamentals of the project should be added to the memory.
    The memory should have concrete examples, project details, and any other relevant information that can help you assist the user later.
    
    For example, you can say "Update Overview to <Project Overview>", or "<Add memory entry: The user is creating a RAG system...>", or "To use this component of the project, do <this> and <that>."
    The request should be clear and concise, specifying what you want to update or add, and in natural language. Any examples you need to add (such as code snippets or project details) should be provided.

    When needed, first check the memory to understand what you already know about the project.
    Always be helpful, informative, and focused on the user's needs.

    When you receive a query, relevant context from your memory will be automatically added to the prompt.
    Use this context to inform your response, but don't repeat it verbatim unless necessary.

    Here is an overview of the project to get you started:
    {overview}""",
    llm_model=model,
)

with rt.Session(logging_setting="VERBOSE", timeout=1000000000):
    rt.context.put("overview", memory.get_overview())
    rt.context.put("memory_keys", memory.list_entries())

    create_sandbox_container()
    try:
        rt.call_sync(
            rag_main_agent, "Hello! I need help with my project. Can you assist me?"
        )
    finally:
        kill_sandbox()
