import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.tools import load_mcp_tools


async def main():
    async with streamablehttp_client(
        url="https://overwatch.railtown.ai/api/mcp/sse",
        headers={
            "Authorization": "a4c3b0de-70e6-4e82-ad64-06777750e6e6:7eqHKq7kn+JTnXGO04CBPDx8s0GVnsaL2mzbVB+ecqo=",
            "Content-Type": "text/event-stream",
        },
    ) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # Get tools
            tools = await load_mcp_tools(session)
            agent = create_react_agent("openai:gpt-4.1", tools)
            math_response = await agent.ainvoke({"messages": "tell me about all errors in the controller file"})


asyncio.run(main())
