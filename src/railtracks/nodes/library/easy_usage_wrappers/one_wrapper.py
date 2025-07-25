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
def get_agent(
    pretty_name: str | None = None,
    *,
    connected_nodes: Iterable[Type[Node] | Callable],
    schema: Type[_TBaseModel],
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
def get_agent(
    pretty_name: str | None = None,
    *,
    schema: Type[_TBaseModel],
    llm_model: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
) -> Type[StructuredLLM[_TBaseModel]]:
    pass


@overload
def get_agent(
    pretty_name: str | None = None,
    *,
    llm_model: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
    return_into: str | None = None,
    format_for_return: Callable[[Any], Any] | None = None,
    format_for_context: Callable[[Any], Any] | None = None,
) -> Type[TerminalLLM]:
    pass


@overload
def get_agent(
    pretty_name: str | None = None,
    *,
    connected_nodes: set[Type[Node] | Callable],
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


def get_agent(
    pretty_name: str | None = None,
    *,
    connected_nodes: set[Type[Node] | Callable] | None = None,
    schema: Type[_TBaseModel] | None = None,
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
    Dynamically creates an agent of your choosing.
    """

    if connected_nodes is not None and len(connected_nodes) > 0:
        if schema is not None:
            return structured_tool_call_llm(
                connected_nodes=connected_nodes,
                schema=schema,
                pretty_name=pretty_name,
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
                connected_nodes=connected_nodes,
                pretty_name=pretty_name,
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
        if schema is not None:
            return structured_llm(
                schema=schema,
                pretty_name=pretty_name,
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
                pretty_name=pretty_name,
                llm_model=llm_model,
                system_message=system_message,
                tool_details=tool_details,
                tool_params=tool_params,
                return_into=return_into,
                format_for_return=format_for_return,
                format_for_context=format_for_context,
            )
