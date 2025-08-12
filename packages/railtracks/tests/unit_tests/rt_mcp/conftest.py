import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import timedelta
from mcp import ClientSession, StdioServerParameters
from railtracks.llm import Parameter
from railtracks.rt_mcp.main import MCPHttpParams
from railtracks.nodes.nodes import Node

# ================= START patch fixtures ================

@pytest.fixture
def reset_patched_flag():
    """Reset the _patched flag to simulate a fresh import."""
    import railtracks.rt_mcp.jupyter_compat
    original_value = railtracks.rt_mcp.jupyter_compat._patched
    railtracks.rt_mcp.jupyter_compat._patched = False
    yield
    # Reset back to original state after test
    railtracks.rt_mcp.jupyter_compat._patched = original_value

@pytest.fixture
def patch_stdio_client():
    cm_mock = AsyncMock()
    cm_mock.__aenter__.return_value = (AsyncMock(), AsyncMock())
    cm_mock.__aexit__.return_value = None
    with patch("railtracks.rt_mcp.main.stdio_client", return_value=cm_mock) as p:
        yield p

@pytest.fixture
def mock_client_session():
    mock = MagicMock(spec=ClientSession)
    mock.initialize = AsyncMock()
    mock.list_tools = AsyncMock(return_value=MagicMock(tools=[{"name": "toolA"}]))
    mock.call_tool = AsyncMock(return_value=MagicMock(content="output"))
    return mock

@pytest.fixture
def patch_ClientSession(mock_client_session):
    cm_mock = AsyncMock()
    cm_mock.__aenter__.return_value = mock_client_session
    cm_mock.__aexit__.return_value = None
    with patch("railtracks.rt_mcp.main.ClientSession", return_value=cm_mock) as p:
        yield p

@pytest.fixture
def patch_streamablehttp_client():
    cm_mock = AsyncMock()
    cm_mock.__aenter__.return_value = (AsyncMock(), AsyncMock())
    cm_mock.__aexit__.return_value = None
    with patch("railtracks.rt_mcp.main.streamablehttp_client", return_value=cm_mock) as p:
        yield p

@pytest.fixture
def patch_sse_client():
    cm_mock = AsyncMock()
    cm_mock.__aenter__.return_value = (AsyncMock(), AsyncMock())
    cm_mock.__aexit__.return_value = None
    with patch("railtracks.rt_mcp.main.sse_client", return_value=cm_mock) as p:
        yield p

@pytest.fixture
def patch_CallbackServer():
    with patch("railtracks.rt_mcp.main.CallbackServer") as p:
        yield p

@pytest.fixture
def patch_OAuthClientProvider():
    with patch("railtracks.rt_mcp.main.OAuthClientProvider") as p:
        yield p

# ================= END patch fixtures =================

# ============ START value/object fixtures =============

@pytest.fixture
def mcp_http_params():
    return MCPHttpParams(
        url="http://test-url",
        headers={"Authorization": "Bearer fake"},
        timeout=timedelta(seconds=23),
        sse_read_timeout=timedelta(seconds=32),
        terminate_on_close=False
    )

@pytest.fixture
def stdio_config():
    return StdioServerParameters(command="dummy", args=[])

@pytest.fixture
def fake_tool():
    obj = MagicMock()
    obj.name = "abc"
    obj.to_dict = MagicMock(return_value={"name": "abc"})
    return obj

class DummyNode(Node):
    @classmethod
    def name(cls):
        return "DummyNode"

@pytest.fixture
def dummy_node():
    return DummyNode()

# ============ END value/object fixtures ===============

# ========== START to_node.py fixtures ===============
@pytest.fixture
def mock_executor_config():
    # You can use a namedtuple, dataclass or a plain MagicMock if not relied on
    return MagicMock(logging_setting="QUIET", timeout=123)

@ pytest.fixture
def mock_params_schema():
    return {
        "type": "object",
        "properties": {
            "foo": {"type": "integer", "description": "A foo parameter"},
            "bar": {"type": "string", "description": "A bar parameter"},
        },
        "required": ["foo"]
    }

@pytest.fixture
def mock_node_info():
    m = MagicMock()
    m.name = "test-tool"
    m.detail = "Docstring here."
    
    ############# ensure they are in sync with mock_params_schema ##########
    foo_param = MagicMock(spec=Parameter)
    foo_param.name = "foo"
    foo_param.param_type = "integer"  # Set actual string value
    foo_param.description = "A foo parameter" 
    foo_param.required = True
    foo_param.default = None
    foo_param.enum = None
    
    bar_param = MagicMock(spec=Parameter)
    bar_param.name = "bar"
    bar_param.param_type = "string"   # Set actual string value
    bar_param.description = "A bar parameter"
    bar_param.required = False
    bar_param.default = None
    bar_param.enum = None
    #########################################################################

    m.parameters = set([foo_param, bar_param])
    return m

@pytest.fixture
def mock_node_cls(mock_node_info):
    # A dummy Node subclass, with tool_info and prepare_tool classmethods
    cls = MagicMock()
    cls.tool_info.return_value = mock_node_info
    cls.prepare_tool = MagicMock()
    cls.node_type = cls
    return cls

@pytest.fixture
def mock_call(monkeypatch):
    # Replace Session with an object that acts as a context manager and supports .run
    call_mock = AsyncMock(return_value=MagicMock(answer="answer123"))
    monkeypatch.setattr("railtracks.interaction.call.call", call_mock)
    return call_mock

@pytest.fixture
def mock_FastMCP():
    with patch("railtracks.rt_mcp.node_to_mcp.FastMCP") as p:
        yield p

@pytest.fixture
def mock_MCPTool():
    with patch("railtracks.rt_mcp.node_to_mcp.MCPTool") as p:
        yield p

@pytest.fixture
def mock_func_metadata():
    with patch("railtracks.rt_mcp.node_to_mcp.func_metadata") as p:
        yield p

# ========== END to_node.py fixtures ===============

# ========== START oauth.py fixtures ==========

@pytest.fixture
def mock_OAuthToken():
    return MagicMock(name='OAuthToken')

@pytest.fixture
def mock_OAuthClientInformationFull():
    return MagicMock(name='OAuthClientInformationFull')

@pytest.fixture
def patch_HTTPServer():
    with patch("railtracks.rt_mcp.oauth.HTTPServer") as p:
        yield p

@pytest.fixture
def patch_threading_Thread():
    with patch("railtracks.rt_mcp.oauth.threading.Thread") as p:
        yield p

@pytest.fixture
def patch_time_sleep():
    with patch("railtracks.rt_mcp.oauth.time.sleep", return_value=None) as p:
        yield p

@pytest.fixture
def patch_time_time(monkeypatch):
    # Simulate time.time advancing to avoid infinite loop in wait_for_callback
    t = [0]
    def fake_time():
        t[0] += 1
        return t[0]
    monkeypatch.setattr("railtracks.rt_mcp.oauth.time.time", fake_time)
    return fake_time

# ========== END oauth.py fixtures =============