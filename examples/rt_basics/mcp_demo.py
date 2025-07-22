import streamlit as st
import asyncio
import railtracks as rt
from railtracks.nodes.library.easy_usage_wrappers.mcp_tool import from_mcp_server
from railtracks.rt_mcp.main import MCPHttpParams

# MCP server URL
urls = [
    "https://remote.mcpservers.org/fetch/mcp",
]

if "node" not in st.session_state:
    print("Initializing MCP tools...")

    # Initialize tools in session state
    async def get_node():
        servers = [from_mcp_server(MCPHttpParams(url=url)) for url in urls]
        all_tools = set(*[server.tools for server in servers])

        return rt.library.tool_call_llm(
            connected_nodes=all_tools,
            pretty_name="Parent Tool",
            system_message=rt.llm.SystemMessage("Provide a response using the tool when asked."),
            model=rt.llm.OpenAILLM("gpt-4o"),
        )

    st.session_state.node = asyncio.run(get_node())


# Initialize chat history in session state
if "history" not in st.session_state:
    st.session_state.history = []

st.title("MCP Chat Demo")

# Chat message display
for msg in st.session_state.history:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"], unsafe_allow_html=True)
    elif msg["role"] == "assistant":
        st.chat_message("assistant").write(msg["content"], unsafe_allow_html=True)

# User input
if prompt := st.chat_input("Type your message..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    async def get_response(history):
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage(m["content"]) if m["role"] == "user" else rt.llm.SystemMessage(m["content"]) for m in history if m["role"] != "assistant"]
        )
        with rt.Runner(executor_config=rt.ExecutorConfig(logging_setting="QUIET", timeout=1000)) as runner:
            response = await runner.run(st.session_state.node, message_history=message_history)
            return response.answer

    # Run async function in Streamlit
    response = asyncio.run(get_response(st.session_state.history))
    st.session_state.history.append({"role": "assistant", "content": response.content})
    st.chat_message("assistant").write(response.content)
