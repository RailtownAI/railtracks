from typing import Type
from ..terminal_llm import TerminalLLM
from ....llm import ModelBase, SystemMessage
from ....llm.tools import Parameter
from requestcompletion.nodes.library.easy_usage_wrappers.node_builder import NodeBuilder


def terminal_llm(  # noqa: C901
    pretty_name: str | None = None,
    *,
    system_message: SystemMessage | str | None = None,
    llm_model: ModelBase | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
) -> Type[TerminalLLM]:
    builder = NodeBuilder(
        TerminalLLM,
        pretty_name=pretty_name,
        class_name="EasyTerminalLLM",
        tool_details=tool_details,
        tool_params=tool_params,
    )
    builder.llm_base(llm_model, system_message)
    if tool_details is not None:
        builder.tool_callable_llm(tool_details, tool_params)

    return builder.build()
