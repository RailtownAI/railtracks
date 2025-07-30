from typing import Any, Callable, Iterable, Type, TypeVar, overload

from pydantic import BaseModel

from railtracks.llm.message import SystemMessage
from railtracks.llm.model import ModelBase
from railtracks.llm.tools.parameter import Parameter
from railtracks.nodes.library import (
    StructuredLLM,
    TerminalLLM,
    structured_llm,
    terminal_llm,
)
from railtracks.nodes.library.easy_usage_wrappers.tool_calling_llms.structured_tool_call_llm import (
    structured_tool_call_llm,
)
from railtracks.nodes.library.easy_usage_wrappers.tool_calling_llms.tool_call_llm import (
    tool_call_llm,
)
from railtracks.nodes.library.tool_calling_llms.structured_tool_call_llm_base import (
    StructuredToolCallLLM,
)
from railtracks.nodes.library.tool_calling_llms.tool_call_llm_base import ToolCallLLM
from railtracks.nodes.nodes import Node

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable],
    output_schema: Type[_TBaseModel],
    llm_model: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
) -> Type[StructuredToolCallLLM[_TBaseModel]]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    output_schema: Type[_TBaseModel],
    llm_model: ModelBase | None = None,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
) -> Type[StructuredLLM[_TBaseModel]]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    llm_model: ModelBase | None = None,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
) -> Type[TerminalLLM]:
    pass


@overload
def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable],
    llm_model: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
) -> Type[ToolCallLLM]:
    pass


def agent_node(
    name: str | None = None,
    *,
    tool_nodes: Iterable[Type[Node] | Callable] | None = None,
    output_schema: Type[_TBaseModel] | None = None,
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
    Dynamically creates an agent based on the provided parameters.

    Args:
        name (str | None): The name of the agent. If none the default will be used.
        tool_nodes (set[Type[Node] | Callable] | None): If your agent is a LLM with access to tools, what does it have access to?
        output_schema (Type[_TBaseModel] | None): If your agent should return a structured output, what is the output_schema?
        llm_model (ModelBase | None): The LLM model to use. If None it will need to be passed in at instance time.
        max_tool_calls (int | None): Maximum number of tool calls allowed (if it is a ToolCall Agent).
        system_message (SystemMessage | str | None): System message for the agent.
        tool_details (str | None): If you are planning to use this as a tool, Details about the tool.
        tool_params (set[Parameter] | None): If you are planning to use this as a tool, Parameters for the tool.
        return_into (str | None): If you would like to return into context what is the key.
        format_for_return (Callable[[Any], Any] | None): Formats the value for return.
        format_for_context (Callable[[Any], Any] | None): Formats the value for the return to context.
    """
    unpacked_tool_nodes: set[Type[Node] | Callable] | None = None
    if tool_nodes is not None:
        unpacked_tool_nodes = set(tool_nodes)


    if unpacked_tool_nodes is not None and len(unpacked_tool_nodes) > 0:
        if output_schema is not None:
            return structured_tool_call_llm(
                tool_nodes=unpacked_tool_nodes,
                output_schema=output_schema,
                name=name,
                llm_model=llm_model,
                max_tool_calls=max_tool_calls,
                system_message=system_message,
                tool_details=tool_details,
                tool_params=tool_params,
                return_into=return_into,
                format_for_return=format_for_return,
                format_for_context=format_for_context,
            )
        else:
            return tool_call_llm(
                tool_nodes=unpacked_tool_nodes,
                name=name,
                llm_model=llm_model,
                max_tool_calls=max_tool_calls,
                system_message=system_message,
                tool_details=tool_details,
                tool_params=tool_params,
                return_into=return_into,
                format_for_return=format_for_return,
                format_for_context=format_for_context,
            )
    else:
        if output_schema is not None:
            return structured_llm(
                output_schema=output_schema,
                name=name,
                llm_model=llm_model,
                system_message=system_message,
                tool_details=tool_details,
                tool_params=tool_params,
                return_into=return_into,
                format_for_return=format_for_return,
                format_for_context=format_for_context,
            )
        else:
            return terminal_llm(
                name=name,
                llm_model=llm_model,
                system_message=system_message,
                tool_details=tool_details,
                tool_params=tool_params,
                return_into=return_into,
                format_for_return=format_for_return,
                format_for_context=format_for_context,
            )
