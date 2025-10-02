import pytest
from railtracks.rt_mcp.node_to_mcp import _create_tool_function, create_mcp_server
from unittest.mock import MagicMock
from mcp.server.fastmcp import FastMCP

# ======= START create_tool_function tests ===========

@pytest.mark.asyncio
@pytest.mark.skip("test failing for unknown reason, needs investigation")
async def test_create_tool_function_signature_and_doc(
    mock_node_cls, mock_node_info, mock_executor_config, mock_call
):
    tool_fn = _create_tool_function(
        node_cls=mock_node_cls,
        node_info=mock_node_info,
    )
    # The function signature should match the output_schema
    sig = tool_fn.__signature__
    assert [p.name for p in sig.parameters.values()] == ["foo", "bar"]
    assert sig.parameters["foo"].default is sig.empty         # Required param
    assert sig.parameters["bar"].default is None              # Optional param

    # Call the function, ensure it runs through the runner and returns answer
    result = await tool_fn(foo=10, bar="hi")
    assert result == "answer123"
    # Ensure runner was called with correct args
    mock_call.assert_awaited()
    args, kwargs = mock_call.call_args
    assert args[0] == mock_node_cls.prepare_tool
    assert args[1] == {"foo": 10, "bar": "hi"}

@pytest.mark.skip("test failing for unknown reason, needs investigation")
def test_create_tool_function_with_no_params(
    mock_node_cls, mock_executor_config, mock_call
):
    # Set .parameters to None, so output_schema is empty
    mock_node_info = MagicMock()
    mock_node_info.parameters = None
    mock_node_info.name = "basic"
    mock_node_info.detail = "detail"
    tool_fn = _create_tool_function(
        node_cls=mock_node_cls,
        node_info=mock_node_info,

    )
    # Should have empty param list
    assert list(tool_fn.__signature__.parameters) == []

# ======= END create_tool_function tests =============


# ======= START create_mcp_server tests ==============
def test_create_mcp_server_new_server_registers_tools(
    mock_FastMCP, mock_MCPTool, mock_func_metadata, mock_node_cls, mock_node_info, mock_params_schema
):
    # Setup
    mcp_instance = MagicMock()
    tool_manager = mcp_instance._tool_manager
    tool_manager._tools = {}

    mock_FastMCP.return_value = mcp_instance
    mock_node_cls.tool_info.return_value = mock_node_info
    # Patch MCPTool and func_metadata for full test
    mock_MCPTool.return_value = "mcp-tool" # so value is easy to check
    mock_func_metadata.return_value = "meta"

    # Patch .to_json_schema to return real dicts for each param, otherwise it'll be a MagicMock
    foo_schema = {"type": "integer", "description": "A foo parameter"}
    bar_schema = {"type": "string", "description": "A bar parameter"}
    for param in mock_node_info.parameters:
        if param.name == "foo":
            param.to_json_schema.return_value = foo_schema
        elif param.name == "bar":
            param.to_json_schema.return_value = bar_schema

    # Call
    result = create_mcp_server(
        nodes=[mock_node_cls],
        server_name="Srv",
        fastmcp=None,
    )

    # Should create new FastMCP and register a tool
    mock_FastMCP.assert_called_with("Srv")
    assert tool_manager._tools[mock_node_info.name] == "mcp-tool"
    tool_args = mock_MCPTool.call_args[1]
    # MCPTool is called with correct fields
    assert tool_args["name"] == mock_node_info.name
    assert tool_args["description"] == mock_node_info.detail
    print(tool_args["parameters"])
    print(mock_params_schema)
    assert tool_args["parameters"] == mock_params_schema
    assert tool_args["fn_metadata"] == "meta"
    assert tool_args["fn"]
    assert result == mcp_instance


def test_create_mcp_rasies_error_if_wrong_type(
        mock_node_cls, mock_executor_config
):
    with pytest.raises(ValueError, match="must be an instance of FastMCP"):
        create_mcp_server([mock_node_cls], fastmcp="notafastmcp")


def test_create_mcp_server_existing_instance(
    mock_MCPTool, mock_func_metadata, mock_node_cls, mock_node_info, mock_executor_config
):
    # Use REAL FastMCP, not a MagicMock!
    fake_mcp = FastMCP("test")
    fake_mcp._tool_manager._tools = {}  # Prepare storage
    # Should use provided instance, not create
    out = create_mcp_server([mock_node_cls], fastmcp=fake_mcp)
    assert out is fake_mcp

def test_create_mcp_server_raises_if_wrong_type(
    mock_node_cls, mock_executor_config
):
    with pytest.raises(ValueError, match="must be an instance of FastMCP"):
        create_mcp_server([mock_node_cls], fastmcp="notafastmcp")

# ======= END create_mcp_server tests =================