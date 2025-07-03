from typing import Type
from ..terminal_llm import TerminalLLM
from ....llm import ModelBase, SystemMessage
from ....llm.tools import Parameter, Tool
from copy import deepcopy
from ....exceptions.node_creation.validation import validate_tool_metadata
from ....exceptions.node_invocation.validation import check_model, check_message_history
from requestcompletion.nodes.library.easy_usage_wrappers._terminal_llm import TerminalBase


def terminal_llm(  # noqa: C901
    pretty_name: str | None = None,
    system_message: SystemMessage | str | None = None,
    model: ModelBase | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
) -> Type[TerminalLLM]:
    class TerminalLLM(TerminalBase,
                          pretty_name=pretty_name,
                          system_message=system_message,
                          model=model,
                          tool_details=tool_details,
                          tool_params=tool_params,):
        @classmethod
        def pretty_name(cls) -> str:
            if pretty_name is None:
                return "TerminalLLM"
            else:
                return pretty_name

    return TerminalLLM
