from typing import Any, Callable, Iterable, Type, TypeVar, Union

from pydantic import BaseModel

from railtracks.llm import (
    ModelBase,
    SystemMessage,
)
from railtracks.nodes._node_builder import NodeBuilder
from railtracks.nodes.library.tool_calling_llms.structured_mess_hist_tool_call_llm import (
    StructuredMessageHistoryToolCallLLM,
)

from ....nodes import Node

_TOutput = TypeVar("_TOutput", bound=BaseModel)


def structured_mess_hist_tool_call_llm(
    connected_nodes: Iterable[Union[Type[Node], Callable]],
    schema: Type[_TOutput],
    *,
    pretty_name: str | None = None,
    llm_model: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: dict | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
):
    """
    Dynamically create a StructuredToolCallLLM node class with custom configuration for tool calling.

    This easy-usage wrapper dynamically builds a node class that supports LLM tool calling where it will return
    the whole message history with a structured output as the last message. This allows you to specify connected
    tools, llm model, schema, system message, tool metadata, and parameters. The returned class can be
    instantiated and used in the railtracks framework on runtime.

    Args:
        connected_nodes (Iterable[Union[Type[Node], Callable]]): The set of node classes or callables that this node can call as tools.
        pretty_name (str, optional): Human-readable name for the node/tool.
        llm_model (ModelBase or None, optional): The LLM model instance to use for this node.
        max_tool_calls (int, optional): Maximum number of tool calls allowed per invocation (default: unlimited).
        system_message (SystemMessage or str or None, optional): The system prompt/message for the node. If not passed here it can be passed at runtime in message history.
        schema (BaseModel): The Pydantic model that defines the structure of the output.
        tool_details (str or None, optional): Description of the node subclass for other LLMs to know how to use this as a tool.
        tool_params (dict or None, optional): Parameters that must be passed if other LLMs want to use this as a tool.

    Returns:
        Type[StructuredToolCallLLM]: The dynamically generated node class with the specified configuration.
    """

    builder = NodeBuilder[StructuredMessageHistoryToolCallLLM[_TOutput]](
        StructuredMessageHistoryToolCallLLM,
        pretty_name=pretty_name,
        class_name="EasyStructuredMessageHistToolCallLLM",
        return_into=return_into,
        format_for_return=format_for_return,
        format_for_context=format_for_context,
    )
    builder.llm_base(llm_model, system_message)
    builder.tool_calling_llm(set(connected_nodes), max_tool_calls)

    if tool_details is not None or tool_params is not None:
        builder.tool_callable_llm(tool_details, tool_params)
    builder.structured(schema)

    return builder.build()
