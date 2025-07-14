from typing import Set, Type, Union, Callable
from requestcompletion.llm import (
    ModelBase,
    SystemMessage,
)

from ....nodes.nodes import Node
from ..easy_usage_wrappers.node_builder import NodeBuilder
from ...library.tool_calling_llms.mess_hist_tool_call_llm import (
    MessageHistoryToolCallLLM,
)


def message_hist_tool_call_llm(  # noqa: C901
    connected_nodes: Set[Union[Type[Node], Callable]],
    pretty_name: str | None = None,
    model: ModelBase | None = None,
    max_tool_calls: int | None = 30,
    system_message: SystemMessage | str | None = None,
    tool_details: str | None = None,
    tool_params: dict | None = None,
) -> Type[MessageHistoryToolCallLLM]:
    builder = NodeBuilder(
        MessageHistoryToolCallLLM,
        pretty_name=pretty_name,
        class_name="EasyMessageHistoryToolCallLLM",
        tool_details=tool_details,
        tool_params=tool_params,
    )
    builder.llm_base(model, system_message)
    builder.tool_calling_llm(connected_nodes, max_tool_calls)
    if tool_details is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
