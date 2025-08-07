"""
Main script for running the RAG-enhanced Project Assistant

This script demonstrates how to use the RAG-enhanced memory context and agent
to create an intelligent project assistant that automatically retrieves relevant
context based on user queries.
"""

import railtracks as rt
from agents import (
    code_execution_agent,
    file_system_agent,
    web_search_agent,
)
from memory_agent import memory, memory_agent

tool_nodes = {
    memory_agent,
    web_search_agent,
    code_execution_agent,
    file_system_agent,
}

rt.context.put("overview", memory.get_overview())


# Create the RAG-enhanced main agent
rag_main_agent = rt.chatui_node(
    pretty_name="RAG-Enhanced Project Assistant",
    tool_nodes=tool_nodes,
    system_message="""You are an intelligent project assistant with advanced project-specific knowledge.
    You have access to a memory system that stores project knowledge, and various tools to help with tasks.
    
    Relevant context from your memory will be automatically provided based on the user's query. 
    The memory system contains a project overview and various memory entries that can be searched.
    This allows you to provide more accurate and helpful responses by leveraging your stored knowledge.
    After any significant interaction, you should update your memory with new information by sending a request.
    For example, you can say "Update Overview to <Project Overview>", or <The user is creating a RAG system..>.
    
    Available specialized agents:
    - Memory Agent: For storing and retrieving project knowledge
    - Web Search Agent: For searching the web for information
    - Notion Agent: For creating notion pages
    - Code Execution Agent: For executing Python code
    - File System Agent: For interacting with the file system
    
    When needed, first check the memory to understand what you already know about the project.
    Always be helpful, informative, and focused on the user's needs.
    
    When you receive a query, relevant context from your memory will be automatically added to the prompt.
    Use this context to inform your response, but don't repeat it verbatim unless necessary.
    
    Here is an overview of the project to get you started:
    {overview}""",
    llm_model=None,
)
