from typing import Any, Callable, Iterable, Type, Union

from requestcompletion.llm import (
    ModelBase,
    SystemMessage,
)
from requestcompletion.nodes._node_builder import NodeBuilder

from ....llm.tools import Parameter
from ....nodes.nodes import Node
from ...library.tool_calling_llms.tool_call_llm import ToolCallLLM


def tool_call_llm(
    connected_nodes: Iterable[Union[Type[Node], Callable]],
    *,
    pretty_name: str | None = None,
    llm_model: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
):
    """
    Dynamically create a ToolCallLLM node class with custom configuration for tool calling.

    This easy-usage wrapper dynamically builds a node class that supports LLM tool calling where it will return
    the last message passed in the history. This allows you to specify connected tools, llm model, system message,
    tool metadata, and parameters. The returned class can be instantiated and used in the requestcompletion
    framework on runtime.

    Args:
        connected_nodes (Iterable[Union[Type[Node], Callable]]): The set of node classes or callables that this node can call as tools.
        pretty_name (str, optional): Human-readable name for the node/tool.
        llm_model (ModelBase or None, optional): The LLM model instance to use for this node.
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
        ToolCallLLM,
        pretty_name=pretty_name,
        class_name="EasyToolCallLLM",
        return_into=return_into,
        format_for_return=format_for_return,
        format_for_context=format_for_context,
    )
    builder.llm_base(llm_model, system_message)
    builder.tool_calling_llm(connected_nodes, max_tool_calls)
    if tool_details is not None or tool_params is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
