import warnings
from typing import TypeVar, Type
from copy import deepcopy
from ....llm import MessageHistory, ModelBase, SystemMessage
from ..structured_llm import StructuredLLM
from pydantic import BaseModel


def structured_llm(
    output_model: Type[BaseModel],
    system_message: SystemMessage | None = None,
    model: ModelBase | None = None,
    pretty_name: str | None = None,
) -> Type[StructuredLLM]:
    class StructuredLLMNode(StructuredLLM):
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
                        "You have provided a model as a parameter and as a class varaible. We will use the parameter."
                    )
            else:
                if model is None:
                    raise RuntimeError("You Must provide a model to the StructuredLLM class")
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

    return StructuredLLMNode
