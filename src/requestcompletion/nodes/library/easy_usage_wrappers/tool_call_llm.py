from typing import Set, Type, Union, Literal, Dict, Any, Callable
from pydantic import BaseModel
from requestcompletion.llm import (
    MessageHistory,
    ModelBase,
    SystemMessage,
    AssistantMessage,
)

from requestcompletion.nodes.nodes import Node
from requestcompletion.nodes.library.easy_usage_wrappers._tool_call_llm import ToolCallBase


def tool_call_llm(  # noqa: C901
    connected_nodes: Set[Union[Type[Node], Callable]],
    pretty_name: str | None = None,
    model: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    output_type: Literal["MessageHistory", "LastMessage"] = "LastMessage",
    output_model: BaseModel | None = None,
    tool_details: str | None = None,
    tool_params: dict | None = None,
) -> Type[ToolCallBase[Union[MessageHistory, AssistantMessage, BaseModel]]]:
    if output_model:
        OutputType = output_model  # noqa: N806
    else:
        OutputType = (  # noqa: N806
            MessageHistory if output_type == "MessageHistory" else AssistantMessage
        )

    if (
        output_model and output_type == "MessageHistory"
    ):  # TODO: add support for MessageHistory output type with output_model. Maybe resp.answer = message_hist and resp.structured = model response
        raise NotImplementedError(
            "MessageHistory output type is not supported with output_model at the moment."
        )

    class ToolCallLLM(ToolCallBase[OutputType],
                      connected_nodes=connected_nodes,
                      pretty_name=pretty_name,
                      model=model,
                      max_tool_calls=max_tool_calls,
                      system_message=system_message,
                      output_type=output_type,
                      output_model=output_model,
                      tool_details=tool_details,
                      tool_params=tool_params,):

        def connected_nodes(self) -> Set[Union[Type[Node], Callable]]:
            return self.__class__._connected_nodes

    return ToolCallLLM
