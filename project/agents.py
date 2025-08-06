"""
Agentic AI Flow with Advanced Project Knowledge and Memory

This module implements an agentic AI flow using railtracks that allows for advanced project-specific knowledge.
It includes a memory module that persists project knowledge between sessions, and various tool agents for
different tasks.
"""

import asyncio
import os
from typing import List

import railtracks as rt


# Web Search Tool
def web_search(query: str, num_results: int = 3) -> str:
    """
    Search the web for information and return summarized results.

    Args:
        query: The search query
        num_results: Number of results to return

    Returns:
        Search results as a formatted string
    """
    # This is a mock implementation. In a real implementation, you would use a search API.
    return (
        f"Web search results for '{query}':\n\n"
        + f"1. Example result 1 for {query}\n"
        + f"2. Example result 2 for {query}\n"
        + f"3. Example result 3 for {query}\n\n"
        + f"These are mock results. In a real implementation, this would use a search API."
    )


# Note-taking Tool
def create_note(title: str, content: str, tags: List[str] = []) -> str:
    """
    Create a new note and store it in memory.

    Args:
        title: The title of the note
        content: The content of the note
        tags: List of tags for categorizing the note

    Returns:
        Confirmation message
    """
    return add_memory(
        "notes", title, content, tags, importance=5, source="note-taking-tool"
    )


def list_notes() -> str:
    """
    List all notes.

    Returns:
        List of notes as a formatted string
    """
    return retrieve_memory("notes")


# Code Execution Tool
def execute_python_code(code: str) -> str:
    """
    Execute Python code in a sandbox environment.

    Args:
        code: The Python code to execute

    Returns:
        Execution result as a string
    """
    # This is a mock implementation. In a real implementation, you would use a sandbox environment.
    return (
        f"Code execution result:\n\n"
        + f"```\n{code}\n```\n\n"
        + f"This is a mock result. In a real implementation, this would execute the code in a sandbox environment."
    )


# File System Tool
def list_files(directory: str = ".") -> str:
    """
    List files in the specified directory.

    Args:
        directory: The directory to list files from

    Returns:
        List of files as a formatted string
    """
    try:
        files = os.listdir(directory)
        return f"Files in directory '{directory}':\n\n" + "\n".join(files)
    except Exception as e:
        return f"Error listing files in directory '{directory}': {str(e)}"


def read_file(file_path: str) -> str:
    """
    Read the contents of a file.

    Args:
        file_path: The path to the file

    Returns:
        File contents as a string
    """
    try:
        with open(file_path, "r") as f:
            content = f.read()
        return f"Contents of file '{file_path}':\n\n{content}"
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"


# Create tool nodes
memory_tools = {
    rt.function_node(add_memory),
    rt.function_node(retrieve_memory),
    rt.function_node(search_memory),
    rt.function_node(delete_memory),
    rt.function_node(summarize_memory),
}

web_tools = {rt.function_node(web_search)}

note_tools = {rt.function_node(create_note), rt.function_node(list_notes)}

code_tools = {rt.function_node(execute_python_code)}

file_tools = {rt.function_node(list_files), rt.function_node(read_file)}

# Combine all tools
all_tools = (
    memory_tools.union(web_tools).union(note_tools).union(code_tools).union(file_tools)
)

# Create the memory agent
memory_agent = rt.agent_node(
    name="Memory Agent",
    tool_nodes=memory_tools,
    system_message="""You are a memory management agent for a project. Your role is to store, retrieve, and manage project-specific knowledge.
    You can add new memories, retrieve existing memories, search for memories, delete memories, and summarize the memory store.
    Always be precise and organized when managing memories. Use appropriate categories and tags to ensure information is easily retrievable.""",
    llm_model="claude-3-5-sonnet-20240620",
)

# Create the web search agent
web_search_agent = rt.agent_node(
    name="Web Search Agent",
    tool_nodes=web_tools,
    system_message="""You are a web search agent. Your role is to search the web for information requested by the user.
    You should provide concise and relevant summaries of the information you find. Always cite your sources.""",
    llm_model="claude-3-5-sonnet-20240620",
)

# Create the note-taking agent
note_taking_agent = rt.agent_node(
    name="Note-Taking Agent",
    tool_nodes=note_tools,
    system_message="""You are a note-taking agent. Your role is to create and manage notes for the user.
    You should organize notes with appropriate titles and tags to ensure they are easily retrievable.""",
    llm_model="claude-3-5-sonnet-20240620",
)

# Create the code execution agent
code_execution_agent = rt.agent_node(
    name="Code Execution Agent",
    tool_nodes=code_tools,
    system_message="""You are a code execution agent. Your role is to execute Python code provided by the user.
    You should provide clear explanations of the code execution results.""",
    llm_model="claude-3-5-sonnet-20240620",
)

# Create the file system agent
file_system_agent = rt.agent_node(
    name="File System Agent",
    tool_nodes=file_tools,
    system_message="""You are a file system agent. Your role is to help the user interact with the file system.
    You can list files in directories and read file contents.""",
    llm_model="claude-3-5-sonnet-20240620",
)

# Create the main agent with access to all specialized agents
main_agent = rt.chatui_node(
    pretty_name="Project Assistant",
    tool_nodes={
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
    },
    system_message="""You are an intelligent project assistant with advanced project-specific knowledge.
    You have access to a memory system that stores project knowledge, and various tools to help with tasks.
    
    Available specialized agents:
    - Memory Agent: For storing and retrieving project knowledge
    - Web Search Agent: For searching the web for information
    - Note-Taking Agent: For creating and managing notes
    - Code Execution Agent: For executing Python code
    - File System Agent: For interacting with the file system
    
    When you start, first check the memory to understand what you already know about the project.
    Always be helpful, informative, and focused on the user's needs.""",
    llm_model="claude-3-5-sonnet-20240620",
)


# Initialize the session with the persistent memory context
def initialize_session():
    """Initialize a session with the persistent memory context."""
    memory_context = PersistentMemoryContext()

    # Register the memory context
    rt.set_config(save_state=True)

    # Return a session with the memory context
    return rt.Session()


# Main function to run the agent
async def run_agent():
    """Run the main agent."""
    with initialize_session() as session:
        # Start the chat UI
        await rt.call(main_agent)


if __name__ == "__main__":
    asyncio.run(run_agent())
