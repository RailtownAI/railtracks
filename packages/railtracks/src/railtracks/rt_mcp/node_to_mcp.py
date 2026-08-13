import inspect
from typing import List

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.tools import Tool as MCPTool
from mcp.server.fastmcp.utilities.func_metadata import func_metadata

from railtracks.built_nodes.concrete import (
    RTFunction,
)

# TODO: this logic must be get refactored
from railtracks.interaction._call import call

# TODO this must be moved to a more appropriate place in utils.
from railtracks.llm.models._litellm_wrapper import _parameters_to_json_schema
from railtracks.nodes.nodes import Node


def _create_tool_function(
    node_cls: Node,
    node_info,
):
    type_map = {
        "integer": int,
        "number": float,
        "string": str,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    params = []
    args_doc = []
    params_schema = (
        _parameters_to_json_schema(node_info.parameters)
        if node_info.parameters is not None
        else {}
    )

    # Get all parameters and sort them: required first, then optional
    all_params = []
    required_params = set(params_schema.get("required", []))

    for param_name, param_info in params_schema.get("properties", {}).items():
        required = param_name in required_params
        param_type = param_info.get("type", "any")
        annotation = type_map.get(param_type, str)
        param_desc = param_info.get("description", "")

        all_params.append((param_name, param_info, required, annotation, param_desc))

    # Sort: required parameters first (True sorts before False when reversed)
    all_params.sort(key=lambda x: not x[2])  # not required = False sorts after True

    # Create parameters in the correct order
    for param_name, param_info, required, annotation, param_desc in all_params:
        if required:
            params.append(
                inspect.Parameter(
                    param_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=annotation,
                )
            )
        else:
            params.append(
                inspect.Parameter(
                    param_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=None,
                    annotation=annotation,
                )
            )

        args_doc.append(f"    {param_name}: {param_desc}")

    async def tool_function(**kwargs):
        return await call(node_cls.prepare_tool, **kwargs)

    tool_function.__signature__ = inspect.Signature(params)
    return tool_function


def create_mcp_server(
    nodes: List[Node | RTFunction],
    server_name: str = "MCP Server",
    fastmcp: FastMCP | None = None,
):
    """
    Create a FastMCP server that can be used to run nodes as MCP tools.

    Args:
        nodes: List of Node classes to be registered as tools with the MCP server.
        server_name: Name of the MCP server instance.
        fastmcp: Optional FastMCP instance to use instead of creating a new one.

    Returns:
        A FastMCP server instance.
    """
    if fastmcp is not None:
        if not isinstance(fastmcp, FastMCP):
            raise ValueError("Provided fastmcp must be an instance of FastMCP.")
        mcp = fastmcp
    else:
        mcp = FastMCP(server_name)

    for node in [n if not hasattr(n, "node_type") else n.node_type for n in nodes]:
        node_info = node.tool_info()
        func = _create_tool_function(node, node_info)

        mcp._tool_manager._tools[node_info.name] = MCPTool(
            fn=func,
            name=node_info.name,
            description=node_info.detail,
            parameters=(
                _parameters_to_json_schema(node_info.parameters)
                if node_info.parameters is not None
                else {}
            ),
            fn_metadata=func_metadata(func, []),
            is_async=True,
            context_kwarg=None,
            annotations=None,
        )  # Register the node as a tool

    return mcp
