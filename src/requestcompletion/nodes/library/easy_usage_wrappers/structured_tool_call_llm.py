from typing import Callable, Literal, Set, Type, Union

from pydantic import BaseModel

from requestcompletion.llm import (
    ModelBase,
    SystemMessage,
)

from ....nodes.nodes import Node
from ...library.tool_calling_llms.structured_tool_call_llm import StructuredToolCallLLM
from ..easy_usage_wrappers.node_builder import NodeBuilder


def structured_tool_call_llm(  # noqa: C901
    connected_nodes: Set[Union[Type[Node], Callable]],
    *,
    pretty_name: str | None = None,
    llm_model: ModelBase | None = None,
    max_tool_calls: int | None = 30,
    system_message: SystemMessage | str | None = None,
    output_type: Literal["MessageHistory", "LastMessage"] = "LastMessage",
    output_model: BaseModel,
    tool_details: str | None = None,
    tool_params: dict | None = None,
) -> Type[StructuredToolCallLLM]:
    """
    Dynamically create a StructuredToolCallLLM node class with custom configuration for tool calling.

    This easy-usage wrapper dynamically builds a node class that supports LLM tool calling where it will return
    a structured output. This allows you to specify connected tools, llm model, output model, system message, tool metadata,
    and parameters. The returned class can be instantiated and used in the requestcompletion framework on runtime.

    Parameters
    ----------
    connected_nodes : Set[Union[Type[Node], Callable]]
        The set of node classes or callables that this node can call as tools.
    pretty_name : str, optional
        Human-readable name for the node/tool.
    llm_model : ModelBase or None, optional
        The LLM model instance to use for this node.
    max_tool_calls : int, optional
        Maximum number of tool calls allowed per invocation (default: 30).
    system_message : SystemMessage or str or None, optional
        The system prompt/message for the node. If not passed here it can be passed at runtime in message history.
    output_type : Literal["MessageHistory", "LastMessage"], optional
        The type of output this node will return. Defaults to "LastMessage".
    output_model : BaseModel
        The Pydantic model that defines the structure of the output.
    tool_details : str or None, optional
        Description of the node subclass for other LLMs to know how to use this as a tool.
    tool_params : dict or None, optional
        Parameters that must be passed if other LLMs want to use this as a tool.

    Returns
    -------
    Type[StructuredToolCallLLM]
        The dynamically generated node class with the specified configuration.

    """
    if (
        output_model and output_type == "MessageHistory"
    ):  # TODO: add support for MessageHistory output type with output_model. Maybe resp.answer = message_hist and resp.structured = model response
        raise NotImplementedError(
            "MessageHistory output type is not supported with output_model at the moment."
        )

    builder = NodeBuilder(
        StructuredToolCallLLM,
        pretty_name=pretty_name,
        class_name="EasyStructuredToolCallLLM",
        tool_details=tool_details,
        tool_params=tool_params,
    )
    builder.llm_base(llm_model, system_message)
    builder.tool_calling_llm(connected_nodes, max_tool_calls)
    if tool_details is not None:
        builder.tool_callable_llm(tool_details, tool_params)
    builder.structured(output_model)

    return builder.build()
