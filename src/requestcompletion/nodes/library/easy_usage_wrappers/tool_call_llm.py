import warnings
from typing import Set, Type, Union, Literal
from copy import deepcopy
from .structured_llm import structured_llm
from .._tool_call_llm_base import OutputLessToolCallLLM
from ...nodes import Node
from ....llm import MessageHistory, ModelBase, SystemMessage, AssistantMessage, UserMessage
from ....interaction.call import call
from ....llm.message import Role
from pydantic import BaseModel


def tool_call_llm(
    connected_nodes: Set[Type[Node]],
    pretty_name: str | None = None,
    model: ModelBase | None = None,
    system_message: SystemMessage | None = None,
    output_type: Literal["MessageHistory", "LastMessage"] = "LastMessage",
    output_model: BaseModel | None = None,
) -> Type[OutputLessToolCallLLM[Union[MessageHistory, AssistantMessage, BaseModel]]]:

    if output_model:
        OutputType = output_model
    else:
        OutputType = MessageHistory if output_type == "MessageHistory" else AssistantMessage

    if (
        output_model and output_type == "MessageHistory"
    ):  # TODO: add support for MessageHistory output type with output_model. Maybe resp.answer = message_hist and resp.structured = model response
        raise NotImplementedError("MessageHistory output type is not supported with output_model at the moment.")

    class ToolCallLLM(OutputLessToolCallLLM[OutputType]):
        def return_output(self):
            if output_model:
                if isinstance(self.structured_output, Exception):
                    raise self.structured_output
                return self.structured_output
            elif output_type == "MessageHistory":
                return self.message_hist
            else:
                return self.message_hist[-1]

        def __init__(
            self,
            message_history: MessageHistory,
            llm_model: ModelBase | None = None,
        ):
            message_history_copy = deepcopy(message_history)
            if system_message is not None:
                if len([x for x in message_history_copy if x.role == Role.system]) > 0:
                    warnings.warn("System message already exists in message history. We will replace it.")
                    message_history_copy = [x for x in message_history_copy if x.role != Role.system]
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
                    raise RuntimeError("You Must provide a model to the ToolCallLLM class")
                llm_model = model

            super().__init__(message_history_copy, llm_model)

            if output_model:
                system_structured = SystemMessage(
                    "You are a structured LLM that can convert the response into a structured output."
                )
                self.structured_resp_node = structured_llm(
                    output_model, system_message=system_structured, model=llm_model
                )

        def connected_nodes(self) -> Set[Type[Node]]:
            return connected_nodes

        @classmethod
        def pretty_name(cls) -> str:
            if pretty_name is None:
                return "ToolCallLLM(" + ", ".join([x.pretty_name() for x in connected_nodes]) + ")"
            else:
                return pretty_name

    return ToolCallLLM
