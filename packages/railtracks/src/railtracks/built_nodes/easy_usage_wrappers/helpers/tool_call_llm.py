from typing import Any, Callable, Iterable, Type, Union

from railtracks.built_nodes._node_builder import NodeBuilder
from railtracks.built_nodes.concrete import ToolCallLLM
from railtracks.built_nodes.concrete.tool_call_llm_base import StreamingToolCallLLM
from railtracks.llm import (
    ModelBase,
    SystemMessage,
)
from railtracks.llm.tools import Parameter
from railtracks.nodes.nodes import Node


def tool_call_llm(
    tool_nodes: Iterable[Union[Type[Node], Callable]],
    *,
    name: str | None = None,
    llm: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
) -> Type[ToolCallLLM | StreamingToolCallLLM]:
    """
    Dynamically create a ToolCallLLM node class with custom configuration for tool calling.

    This easy-usage wrapper dynamically builds a node class that supports LLM tool calling where it will return
    the last message passed in the history. This allows you to specify connected tools, llm model, system message,
    tool metadata, and parameters. The returned class can be instantiated and used in the railtracks
    framework on runtime.

    Args:
        tool_nodes (Iterable[Union[Type[Node], Callable]]): The set of node classes or callables that this node can call as tools.
        name (str, optional): Human-readable name for the node/tool.
        llm (ModelBase or None, optional): The LLM model instance to use for this node.
        max_tool_calls (int, optional): Maximum number of tool calls allowed per invocation (default: unlimited).
        system_message (SystemMessage or str or None, optional): The system prompt/message for the node. If not passed here it can be passed at runtime in message history.
        tool_details (str or None, optional): Description of the node subclass for other LLMs to know how to use this as a tool.
        tool_params (set of params or None, optional): Parameters that must be passed if other LLMs want to use this as a tool.
        return_into (str, optional): The key to store the result of the tool call into context. If not specified, the result will not be put into context.
        format_for_return (Callable[[Any], Any] | None, optional): A function to format the result before returning it, only if return_into is provided. If not specified when while return_into is provided, None will be returned.
        format_for_context (Callable[[Any], Any] | None, optional): A function to format the result before putting it into context, only if return_into is provided. If not provided, the response will be put into context as is.

    Returns:
        Type[ToolCallLLM]: The dynamically generated node class with the specified configuration.
    """
    builder = NodeBuilder(
        StreamingToolCallLLM if llm is not None and llm.stream else ToolCallLLM,
        name=name,
        class_name="EasyToolCallLLM",
        return_into=return_into,
        format_for_return=format_for_return,
        format_for_context=format_for_context,
    )
    builder.llm_base(llm, system_message)
    builder.tool_calling_llm(tool_nodes, max_tool_calls)
    if tool_details is not None or tool_params is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
