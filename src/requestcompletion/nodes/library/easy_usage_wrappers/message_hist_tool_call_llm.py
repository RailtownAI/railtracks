from typing import Set, Type, Union, Literal, Dict, Any, Callable
from pydantic import BaseModel
from requestcompletion.llm import (
    MessageHistory,
    ModelBase,
    SystemMessage,
    AssistantMessage,
)

from ....nodes.nodes import Node
from ..easy_usage_wrappers.node_builder import NodeBuilder
from ...library.tool_calling_llms.mess_hist_tool_call_llm import MessageHistoryToolCallLLM


def tool_call_llm(  # noqa: C901
    connected_nodes: Set[Union[Type[Node], Callable]],
    pretty_name: str | None = None,
    model: ModelBase | None = None,
    max_tool_calls: int | None = 30,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: dict | None = None,
) -> Type[MessageHistoryToolCallLLM[Union[MessageHistory, AssistantMessage, BaseModel]]]:

    builder = NodeBuilder(
        MessageHistoryToolCallLLM[MessageHistory],
        pretty_name=pretty_name,
        class_name="EasyToolCallLLM",
    )
    builder.llm_base(model, system_message)
    builder.tool_calling_llm(connected_nodes, max_tool_calls)
    if tool_details is not None:
        builder.override_tool_details(tool_details, tool_params)
        builder.override_tool_details(tool_details, tool_params)
    
    return builder.build()
