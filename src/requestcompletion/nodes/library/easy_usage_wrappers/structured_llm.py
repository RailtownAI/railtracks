import warnings
from copy import deepcopy
from typing import Any, Dict, Type

from pydantic import BaseModel
from typing_extensions import Self

from ....exceptions.node_creation.validation import validate_tool_metadata
from ....exceptions.node_invocation.validation import check_message_history, check_model
from ....llm import (
    MessageHistory,
    ModelBase,
    SystemMessage,
    Tool,
    UserMessage,
)
from ....nodes.library.structured_llm import StructuredLLM


def structured_llm(  # noqa: C901
    output_model: Type[BaseModel],
    system_message: SystemMessage | str | None = None,
    model: ModelBase | None = None,
    pretty_name: str | None = None,
    tool_details: str | None = None,
    tool_params: dict | None = None,
) -> Type[StructuredLLM]:
    class StructuredLLMNode(StructuredLLM):
        def __init__(
            self,
            message_history: MessageHistory,
            llm_model: ModelBase | None = None,
        ):
            check_message_history(
                message_history, system_message
            )  # raises error if message_history is not valid
            message_history_copy = deepcopy(message_history)
            if system_message is not None:
                if len([x for x in message_history_copy if x.role == "system"]) > 0:
                    warnings.warn(
                        "System message already exists in message history. We will replace it."
                    )
                    message_history_copy = [
                        x for x in message_history_copy if x.role != "system"
                    ]
                    message_history_copy.insert(0, system_message)
                else:
                    message_history_copy.insert(0, system_message)

            if llm_model is not None:
                if model is not None:
                    warnings.warn(
                        "You have provided a model as a parameter and as a class varaible. We will use the parameter."
                    )
            else:
                check_model(model)  # raises error if model is not valid
                llm_model = model

            super().__init__(message_history=message_history_copy, model=llm_model)

        @classmethod
        def output_model(cls) -> Type[BaseModel]:
            return output_model

        @classmethod
        def pretty_name(cls) -> str:
            if pretty_name is None:
                return output_model.__name__
            else:
                return pretty_name

        @classmethod
        def tool_info(cls):
            return Tool(
                name=cls.pretty_name().replace(" ", "_"),
                detail=tool_details,
                parameters=tool_params,
            )

        @classmethod
        def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
            message_hist = MessageHistory(
                [
                    UserMessage(f"{param.name}: '{tool_parameters[param.name]}'")
                    for param in (tool_params if tool_params else [])
                ]
            )
            return cls(message_hist)

    validate_tool_metadata(tool_params, tool_details, system_message, pretty_name)
    if system_message is not None and isinstance(
        system_message, str
    ):  # system_message is a string, (tackled at the time of node creation)
        system_message = SystemMessage(system_message)

    return StructuredLLMNode
