import warnings
from typing import Type, Dict, Any
from ..terminal_llm import TerminalLLM
from ....llm import MessageHistory, ModelBase, SystemMessage, UserMessage
from ....llm.tools import Parameter, Tool
from copy import deepcopy


def terminal_llm(
    pretty_name: str | None = None,
    system_message: SystemMessage | None = None,
    model: ModelBase | None = None,
    tool_details: str | None = None,
    tool_params: set[Parameter] | None = None,
) -> Type[TerminalLLM]:
    class TerminalLLMNode(TerminalLLM):
        def __init__(
            self,
            message_history: MessageHistory,
            llm_model: ModelBase | None = None,
        ):
            message_history_copy = deepcopy(message_history)
            if system_message is not None:
                if len([x for x in message_history_copy if x.role == "system"]) > 0:
                    warnings.warn("System message already exists in message history. We will replace it.")
                    message_history_copy = [x for x in message_history_copy if x.role != "system"]
                    message_history_copy.insert(0, system_message)
                else:
                    message_history_copy.insert(0, system_message)

            if llm_model is not None:
                if model is not None:
                    warnings.warn(
                        "You have provided a model as a parameter and as a class variable. We will use the parameter."
                    )
            else:
                if model is None:
                    raise RuntimeError("You Must provide a model to the TerminalLLM class")
                llm_model = model

            super().__init__(message_history=message_history_copy, model=llm_model)

        @classmethod
        def pretty_name(cls) -> str:
            if pretty_name is None:
                if tool_details:  # at this point if tool_details is not None, then terminal_llm is being used as a tool
                    raise RuntimeError(
                        "You must provide a pretty_name when using TerminalLLM as a tool, as this is used to identify the tool."
                    )
                return "TerminalLLM"
            else:
                return pretty_name

        if tool_details:  # params might be empty

            @classmethod
            def tool_info(cls) -> Tool:
                return Tool(
                    name=cls.pretty_name().replace(" ", "_"),
                    detail=tool_details,
                    parameters=tool_params,
                )

            @classmethod
            def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> TerminalLLM:
                message_hist = MessageHistory(
                    [
                        UserMessage(f"{param.name}: '{tool_parameters[param.name]}'")
                        for param in (tool_params if tool_params else [])
                    ]
                )
                return cls(message_hist)

    if tool_params and not tool_details:
        raise RuntimeError("Tool parameters provided but no tool details provided.")
    elif tool_details and tool_params is not None and len(tool_params) == 0:
        raise RuntimeError("If you want no params for the tool, tool_params must be set to None.")
    elif tool_details and tool_params and len([x.name for x in tool_params]) != len(set([x.name for x in tool_params])):
        raise ValueError("Duplicate parameter names are not allowed")

    return TerminalLLMNode
