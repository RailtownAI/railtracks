import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from requestcompletion.rc_mcp.main import MCPHttpParams, MCPAsyncClient, from_mcp

# ============= START MCPHttpParams tests =============

def test_mcp_httpparams_defaults():
    params = MCPHttpParams(url="abc")
    assert params.url == "abc"
    assert params.headers is None
    assert params.timeout.total_seconds() == 30
    assert params.sse_read_timeout.total_seconds() == 60 * 5
    assert params.terminate_on_close is True

def test_mcp_httpparams_custom(mcp_http_params):
    assert mcp_http_params.url == "http://test-url"
    assert mcp_http_params.headers == {"Authorization": "Bearer fake"}
    assert mcp_http_params.timeout.total_seconds() == 23
    assert mcp_http_params.sse_read_timeout.total_seconds() == 32
    assert mcp_http_params.terminate_on_close is False

# ============== END MCPHttpParams tests ==============

# ======== START MCPAsyncClient context tests =========

@pytest.mark.asyncio
async def test_async_client_enter_exit_stdio(
    stdio_config,
    mock_client_session,
    # DO NOT REMOVE: these patched mocks are set up in conftest and being used in the test in the background
    patch_stdio_client,
    patch_ClientSession,
):
    # ClientSession and stdio_client are now context managers set up by the fixtures
    async with MCPAsyncClient(stdio_config) as client:
        assert isinstance(client, MCPAsyncClient)
        assert client.session == mock_client_session

@pytest.mark.asyncio
async def test_async_client_enter_exit_http(
    mcp_http_params,
    patch_httpx_AsyncClient,
    # DO NOT REMOVE: these patched mocks are set up in conftest and being used in the test in the background
    patch_streamablehttp_client,
    patch_ClientSession,
):
    # Patch HTTPX client to return no oauth metadata
    patch_httpx_AsyncClient.return_value.__aenter__.return_value.get.return_value.status_code = 404
    async with MCPAsyncClient(mcp_http_params) as client:
        assert isinstance(client, MCPAsyncClient)

# ========== END MCPAsyncClient context tests =========


# ===== START MCPAsyncClient.list_tools/call_tool tests ====
@pytest.mark.asyncio
async def test_async_client_list_tools_caching(
    mock_client_session,
    stdio_config,
):
    client = MCPAsyncClient(stdio_config, client_session=mock_client_session)
    # no cache first time
    tools = await client.list_tools()
    assert tools == [{"name": "toolA"}]
    # Should return cached value now (client._tools_cache)
    tools2 = await client.list_tools()
    assert tools2 == [{"name": "toolA"}]
    assert mock_client_session.list_tools.call_count == 1

@pytest.mark.asyncio
async def test_async_client_call_tool(mock_client_session, stdio_config):
    client = MCPAsyncClient(stdio_config, client_session=mock_client_session)
    result = await client.call_tool("toolA", {"x": 2})
    assert result.content == "output"
    mock_client_session.call_tool.assert_awaited_with("toolA", {"x": 2})

# ====== END MCPAsyncClient.list_tools/call_tool tests ===

# =============== START MCPAsyncClient _init_http tests ============
@pytest.mark.asyncio
async def test_async_client_init_http_uses_correct_transport(
    mcp_http_params,
    patch_httpx_AsyncClient,
    # DO NOT REMOVE: these patched mocks are set up in conftest and being used in the test in the background
    patch_streamablehttp_client,
    patch_sse_client,
    patch_ClientSession,
    mock_client_session
):
    # SSE URL usage
    mcp_http_params.url = "https://host.com/api/sse"
    patch_httpx_AsyncClient.return_value.__aenter__.return_value.get.return_value.status_code = 404
    client = MCPAsyncClient(mcp_http_params)
    await client._init_http()
    assert client.transport_type == "sse"

    # Streamable HTTP usage
    mcp_http_params.url = "https://host.com/api/other"
    await client._init_http()
    assert client.transport_type == "streamable_http"

@pytest.mark.asyncio
async def test_async_client_init_http_oauth_flow(
    mcp_http_params,
    patch_httpx_AsyncClient,
    # DO NOT REMOVE: these patched mocks are set up in conftest and being used in the test in the background
    patch_streamablehttp_client,
    patch_CallbackServer,
    patch_OAuthClientProvider,
    patch_ClientSession,
    mock_client_session
):
    # Simulate OAuth server presence
    mcp_http_params.url = "http://mock-oauth-server"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"issuer": "x"}
    patch_httpx_AsyncClient.return_value.__aenter__.return_value.get.return_value = mock_response

    client = MCPAsyncClient(mcp_http_params)
    await client._init_http()
    assert client.transport_type in ("sse", "streamable_http")

# ============== END MCPAsyncClient _init_http tests ===============

# =============== START from_mcp tests =================

def test_from_mcp_returns_node_class(fake_tool, mcp_http_params):
    result_class = from_mcp(fake_tool, mcp_http_params)
    node = result_class(bar=1)
    # must have custom pretty_name
    assert result_class.pretty_name() == f"MCPToolNode({fake_tool.name})"
    # must have correct tool_info
    with patch.object(result_class, 'tool_info', wraps=result_class.tool_info) as ti:
        Tool = type("Tool", (), {"from_mcp": staticmethod(lambda tool: "X")})
        result_class.tool_info = classmethod(lambda cls: Tool.from_mcp(fake_tool))
        assert result_class.tool_info() == "X"

def test_from_mcp_prepare_tool(fake_tool, mcp_http_params):
    result_class = from_mcp(fake_tool, mcp_http_params)
    options = {"one": 1, "two": 2}
    inst = result_class.prepare_tool(options)
    assert isinstance(inst, result_class)
    assert inst.kwargs == options

@pytest.mark.asyncio
async def test_from_mcp_invoke(fake_tool, mcp_http_params):
    result_class = from_mcp(fake_tool, mcp_http_params)
    node = result_class(bar=2)
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.call_tool.return_value = MagicMock(content="abc")
    node.client = mock_client
    result = await node.invoke()
    assert result == "abc"

    # also test no content attr
    mock_client.call_tool.return_value = "valonly"
    result = await node.invoke()
    assert result == "valonly"

# =============== END from_mcp tests ==================