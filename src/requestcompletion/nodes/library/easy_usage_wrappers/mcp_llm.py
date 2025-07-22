from typing import Any, Callable, Type
from pydantic import BaseModel

from requestcompletion.llm import (
    ModelBase,
    SystemMessage,
)
from requestcompletion.nodes._node_builder import NodeBuilder

from ....llm.tools import Parameter
from ....nodes.nodes import Node
from ...library.tool_calling_llms.tool_call_llm import ToolCallLLM
from requestcompletion.nodes.library.easy_usage_wrappers.mcp_tool import from_mcp_server
from requestcompletion.rc_mcp.main import MCPStdioParams

def tool_call_llm(  # noqa: 
    pretty_name: str | None = None,
    mcp_command : str | None = None, 
    mcp_args : list[str] | None = None, 
    mcp_env : dict[str, str] | None = None,
    *,
    llm_model: ModelBase | None = None,
    max_tool_calls: int | None = None,
    last_message : bool | None = True,
    schema : BaseModel | None = None, 
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
) -> Type[ToolCallLLM]:
    """
    Dynamically create an MCPToolCallLLM node class with custom configuration for tool calling and output.

    This easy-usage wrapper dynamically builds a node class that supports LLM tool calling where it will return
    the specified type. This allows you to specify the return type, llm model, system message,
    tool metadata, and parameters. The returned class can be instantiated and used in the requestcompletion
    framework on runtime.

    Args:
        mcp_command (str, optional): The command to run the MCP server (e.g., 'npx').
        mcp_args (list[str], optional): Arguments to pass to the MCP server command. These specify which MCP server or tool to launch and how.
        mcp_env (dict[str, str], optional): Environment variables to set for the MCP server process.
        pretty_name (str, optional): Human-readable name for the node/tool.
        llm_model (ModelBase or None, optional): The LLM model instance to use for this node.
        max_tool_calls (int, optional): Maximum number of tool calls allowed per invocation (default: unlimited).
        last_message (bool, optional): Dictates whether you are returned just the last message or whole message history. Defaults to just the last message.
        schema (BaseModel, optional) : The Pydantic model that defines the structure of the output. Defaults to no structure.
        system_message (SystemMessage or str or None, optional): The system prompt/message for the node. If not passed here it can be passed at runtime in message history.
        tool_details (str or None, optional): Description of the node subclass for other LLMs to know how to use this as a tool.
        tool_params (set of params or None, optional): Parameters that must be passed if other LLMs want to use this as a tool.
        return_into (str, optional): The key to store the result of the tool call into context. If not specified, the result will not be put into context.
        format_for_return (Callable[[Any], Any] | None, optional): A function to format the result before returning it, only if return_into is provided. If not specified when while return_into is provided, None will be returned.
        format_for_context (Callable[[Any], Any] | None, optional): A function to format the result before putting it into context, only if return_into is provided. If not provided, the response will be put into context as is.

    Returns:
        Type[ToolCallLLM]: The dynamically generated node class with the specified configuration.
    """
    if schema:
        if last_message:
            tool_call_type = StructuredToolCallLLM
        else:
            tool_call_type = StructuredMessageHistoryToolCallLLM
    else:
        if last_message:
            tool_call_type = ToolCallLLM
        else:
            tool_call_type = MessageHistoryToolCallLLM
    
    builder = NodeBuilder(
    tool_call_type,
    pretty_name=pretty_name,
    class_name="MCPToolCallLLM",
    return_into=return_into,
    format_for_return=format_for_return,
    format_for_context=format_for_context,
    )

    builder.llm_base(llm_model, system_message)
    tools = from_mcp_server(
            MCPStdioParams(
                command=mcp_command,
                args=mcp_args,
                env=mcp_env,
            )
        )
    connected_nodes = {*tools}
    
    builder.tool_calling_llm(connected_nodes, max_tool_calls)
    if tool_details is not None or tool_params is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
