"""
Agentic AI Flow with Advanced Project Knowledge and Memory

This module implements an agentic AI flow using railtracks that allows for advanced project-specific knowledge.
It includes a memory module that persists project knowledge between sessions, and various tool agents for
different tasks.
"""

import os

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
        + "These are mock results. In a real implementation, this would use a search API."
    )


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
        "Code execution result:\n\n"
        + f"```\n{code}\n```\n\n"
        + "This is a mock result. In a real implementation, this would execute the code in a sandbox environment."
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


web_tools = {rt.function_node(web_search)}

code_tools = {rt.function_node(execute_python_code)}

file_tools = {rt.function_node(list_files), rt.function_node(read_file)}

# Create the web search agent
web_search_agent = rt.agent_node(
    name="Web Search Agent",
    tool_nodes=web_tools,
    system_message="""You are a web search agent. Your role is to search the web for information requested by the user.
    You should provide concise and relevant summaries of the information you find. Always cite your sources.""",
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
