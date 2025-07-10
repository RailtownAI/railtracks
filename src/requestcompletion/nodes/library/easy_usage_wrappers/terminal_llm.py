from typing import Type
from ..terminal_llm import TerminalLLM
from ....llm import ModelBase, SystemMessage
from ....llm.tools import Parameter, Tool
from copy import deepcopy
from ....exceptions.node_creation.validation import validate_tool_metadata
from ....exceptions.node_invocation.validation import check_model, check_message_history
from requestcompletion.nodes.library.easy_usage_wrappers.node_builder import NodeBuilder


def terminal_llm(  # noqa: C901
    pretty_name: str | None = None,
    system_message: SystemMessage | str | None = None,
    model: ModelBase | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
) -> Type[TerminalLLM]:
    
    builder = NodeBuilder(TerminalLLM, 
                          pretty_name=pretty_name, 
                          class_name="EasyTerminalLLM", 
                          tool_details=tool_details, 
                          tool_params=tool_params,
                          )
    builder.llm_base(model, system_message)
    if tool_details is not None:
        builder.tool_callable_llm(tool_details, tool_params)
        

    return builder.build()
