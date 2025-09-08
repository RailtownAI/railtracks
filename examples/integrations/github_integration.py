##################################################################
# For this example, ensure you have a valid GitHub PAT token set
# in the environment variables.
##################################################################
import os

from railtracks import MCPHttpParams, connect_mcp
import asyncio
import railtracks as rt

server = connect_mcp(
    MCPHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": f"Bearer {os.getenv('GITHUB_PAT_TOKEN')}",
        },
    )
)
tools = server.tools
##################################################################
# Example using the tools with an agent


agent = rt.agent_node(
    tool_nodes={*tools},
    system_message="""You are a GitHub Copilot agent that can interact with GitHub repositories.""",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Tell me about the RailtownAI/rc repository on GitHub."""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

async def call_node():
    with rt.Session(logging_setting="VERBOSE"):
        result = await rt.call(agent, message_history)

    print(result.content)

asyncio.run(call_node())

