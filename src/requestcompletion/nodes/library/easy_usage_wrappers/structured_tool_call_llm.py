from typing import Set, Type, Union, Literal, Callable
from pydantic import BaseModel
from requestcompletion.llm import (
    ModelBase,
    SystemMessage,
)

from ....nodes.nodes import Node
from ..easy_usage_wrappers.node_builder import NodeBuilder
from ...library.tool_calling_llms.structured_tool_call_llm import StructuredToolCallLLM


def structured_tool_call_llm(  # noqa: C901
    connected_nodes: Set[Union[Type[Node], Callable]],
    pretty_name: str | None = None,
    llm_model: ModelBase | None = None,
    max_tool_calls: int | None = 30,
    system_message: SystemMessage | str | None = None,
    output_type: Literal["MessageHistory", "LastMessage"] = "LastMessage",
    output_model: BaseModel | None = None,
    tool_details: str | None = None,
    tool_params: dict | None = None,
) -> Type[StructuredToolCallLLM]:
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
