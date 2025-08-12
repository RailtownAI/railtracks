"""
Main script for running the RAG-enhanced Project Assistant

This script demonstrates how to use the RAG-enhanced memory context and agent
to create an intelligent project assistant that automatically retrieves relevant
context based on user queries.
"""

import railtracks as rt
from custom_chat_ui import custom_chatui_node
from memory_agent import memory, memory_agent
from railtracks.llm.models.api_providers import OpenAILLM

from examples.integrations.sandbox_python_integration import (
    create_sandbox_container,
    execute_code,
    kill_sandbox,
)
from examples.integrations.webseach_integration import fetch_mcp_tools, google_search

tool_nodes = [memory_agent, google_search, execute_code] + fetch_mcp_tools

# Create the RAG-enhanced main agent
rag_main_agent = custom_chatui_node(
    pretty_name="RAG-Enhanced Project Assistant",
    tool_nodes=tool_nodes,
    system_message="""You are an intelligent project assistant with advanced project-specific knowledge.
    You have access to a memory system that stores project knowledge, and various tools to help with tasks.

    Relevant context from your memory will be automatically provided based on the user's query. 
    The memory system contains a project overview and various memory entries that can be searched if you need to remember anything else.
    
    This allows you to provide more accurate and helpful responses by leveraging your stored knowledge.

    When needed, first check the memory to understand what you already know about the project.
    Always be helpful, informative, and focused on the user's needs.

    When you receive a query, relevant context from your memory will be automatically added to the prompt.
    Use this context to inform your response, but don't repeat it verbatim unless necessary.

    Here is an overview of the project to get you started:
    {overview}""",
    llm_model=OpenAILLM(model_name="gpt-4o"),
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
