
# --8<-- [start: github_mcp]
import os
from railtracks.rt_mcp import MCPHttpParams
from railtracks import connect_mcp

server = connect_mcp(
    MCPHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": f"Bearer {os.getenv('GITHUB_PAT_TOKEN')}",
        },
    )
)
tools = server.tools
# --8<-- [end: github_mcp]

# --8<-- [start: github_call]
import railtracks as rt
import asyncio

agent = rt.agent_node(
    # tool_nodes={*tools},    # Uncomment this line to use the tools
    system_message="""You are a GitHub Copilot agent that can interact with GitHub repositories.""",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Tell me about the RailtownAI/rc repository on GitHub."""

async def call_node():
    with rt.Session():
        result = await rt.call(agent, user_prompt)

    print(result.content)

# asyncio.run(call_node())
# --8<-- [end: github_call]

# --8<-- [start: notion_mcp]
import json
import os
from railtracks import MCPStdioParams, connect_mcp

MCP_COMMAND = "npx"
MCP_ARGS = ["-y", "@notionhq/notion-mcp-server"]
NOTION_VERSION = "2022-06-28"

headers = {
    "Authorization": f"Bearer {os.environ['NOTION_API_TOKEN']}",
    "Notion-Version": NOTION_VERSION
}

notion_env = {
    "OPENAPI_MCP_HEADERS": json.dumps(headers)
}

server = connect_mcp(
    MCPStdioParams(
        command=MCP_COMMAND,
        args=MCP_ARGS,
        env=notion_env,
    )
)
tools = server.tools
# --8<-- [end: notion_mcp]

# --8<-- [start: notion_call]
import railtracks as rt
import asyncio
agent = rt.agent_node(
    # tool_nodes={*tools},    # Uncomment this line to use the tools
    system_message="""You are a master Notion page designer. You love creating beautiful
     and well-structured Notion pages and make sure that everything is correctly formatted.""",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Create a new page in Notion called 'Jokes' under the parent page "Welcome to Notion!" with a small joke at the top of the page."""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

async def call_node():
    with rt.Session():
        result = await rt.call(agent, message_history)

    print(result.content)

# asyncio.run(call_node())
# --8<-- [end: notion_call]

# --8<-- [start: sandbox_setup]
import subprocess
import railtracks as rt

def create_sandbox_container():
    subprocess.run([
        "docker", "run", "-dit", "--rm",
        "--name", "sandbox_chatbot_session",
        "--memory", "512m", "--cpus", "0.5",
        "python:3.12-slim", "python3"
    ])


def kill_sandbox():
    subprocess.run(["docker", "rm", "-f", "sandbox_chatbot_session"])


def execute_code(code: str) -> str:
    exec_result = subprocess.run([
        "docker", "exec", "sandbox_chatbot_session",
        "python3", "-c", code
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return exec_result.stdout.decode() + exec_result.stderr.decode()


agent = rt.agent_node(
    tool_nodes={execute_code},
    system_message="""You are a master python programmer. To execute code, you have access to a sandboxed Python environment.
    You can execute code in it using run_in_sandbox.
    You can only see the output of the code if it is printed to stdout or stderr, so anything you want to see must be printed.
    You can install packages with code like 'import os; os.system('pip install numpy')'""",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)
# --8<-- [end: sandbox_setup]

# --8<-- [start: sandbox_call]
user_prompt = """Create a 3x3 array of random numbers using numpy, and print the array and its mean"""

async def call_node():
    with rt.Session(logging_setting="VERBOSE"):
        create_sandbox_container()
        try:
            result = await rt.call(agent, user_prompt)
        finally:
            kill_sandbox()

    print(result.content)

# asyncio.run(call_node())
# --8<-- [end: sandbox_call]

# --8<-- [start: bash_tool]
import subprocess

def run_shell(command: str) -> str:
    """Run a bash command and return its output or error."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr.strip()}"
    except Exception as e:
        return f"Exception: {str(e)}"


bash_tool = rt.function_node(run_shell)
# --8<-- [end: bash_tool]

# --8<-- [start: bash_call]
import platform
import railtracks as rt
import asyncio

agent = rt.agent_node(
    tool_nodes={bash_tool},
    system_message=f"You are a useful helper that can run local shell commands. "
                   f"You are on a {platform.system()} machine. Use appropriate shell commands to answer the user's questions.",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """What directories are in the current directory?"""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

async def call_node():
    with rt.Session(logging_setting="VERBOSE"):
        result = await rt.call(agent, message_history)

    print(result.content)

# asyncio.run(call_node())
# --8<-- [end: bash_call]

# --8<-- [start: slack_mcp]
import os
from railtracks import connect_mcp, MCPStdioParams

MCP_COMMAND = "npx"
MCP_ARGS = ["-y", "@modelcontextprotocol/server-slack"]

slack_env = {
    "SLACK_BOT_TOKEN": os.environ['SLACK_BOT_TOKEN'],
    "SLACK_TEAM_ID": os.environ['SLACK_TEAM_ID'],
    "SLACK_CHANNEL_IDS": os.environ['SLACK_CHANNEL_IDS'],
}

server = connect_mcp(
    MCPStdioParams(
        command=MCP_COMMAND,
        args=MCP_ARGS,
        env=slack_env,
    )
)
tools = server.tools
# --8<-- [end: slack_mcp]

# --8<-- [start: slack_call]
import railtracks as rt
import asyncio

agent = rt.agent_node(
    # tool_nodes={*tools},    # Uncomment this line to use the tools
    system_message="""You are a Slack agent that can interact with Slack channels.""",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Send a message to general saying "Hello!"."""

async def call_node():
    with rt.Session(logging_setting="VERBOSE"):
        result = await rt.call(agent, user_prompt)

    print(result.content)

# asyncio.run(call_node())
# --8<-- [end: slack_call]

# --8<-- [start: websearch_imports]
from dotenv import load_dotenv
import os
from railtracks import connect_mcp
import railtracks as rt
import asyncio
from railtracks.rt_mcp import MCPHttpParams
import aiohttp
from typing import Dict, Any

load_dotenv()
# --8<-- [end: websearch_imports]

# --8<-- [start: fetch_mcp_server]
# MCP Tools that can fetch data from URLs
fetch_mcp_server = connect_mcp(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
fetch_mcp_tools = fetch_mcp_server.tools
# --8<-- [end: fetch_mcp_server]

# --8<-- [start: google_search]
def _format_results(data: Dict[str, Any]) -> Dict[str, Any]:
   ...


@rt.function_node
async def google_search(query: str, num_results: int = 3) -> Dict[str, Any]:
   """
   Tool for searching using Google Custom Search API
   
   Args:
       query (str): The search query
       num_results (int): The number of results to return (max 5)
   
   Returns:
       Dict[str, Any]: Formatted search results
   """
   params = {
      'key': os.environ['GOOGLE_SEARCH_API_KEY'],
      'cx': os.environ['GOOGLE_SEARCH_ENGINE_ID'],
      'q': query,
      'num': min(num_results, 5)  # Google API maximum is 5
   }

   async with aiohttp.ClientSession() as session:
      try:
         async with session.get("https://www.googleapis.com/customsearch/v1", params=params) as response:
            if response.status == 200:
               data = await response.json()
               return _format_results(data)
            else:
               error_text = await response.text()
               raise Exception(f"Google API error {response.status}: {error_text}")
      except Exception as e:
         raise Exception(f"Search failed: {str(e)}")
# --8<-- [end: google_search]

# --8<-- [start: websearch_agent]
# Combine all tools
tools = fetch_mcp_tools + [google_search]

# Create the agent with search capabilities
agent = rt.agent_node(
    # tool_nodes={*tools},    # Uncomment this line to use the tools
    system_message="""You are an information gathering agent that can search the web.""",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

# Example usage
user_prompt = """Tell me about Railtown AI."""
async def call_node():
    result = await rt.call(agent, message_history)
    print(result)

# asyncio.run(call_node())
# --8<-- [end: websearch_agent]