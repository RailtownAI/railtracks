from ._tool_call_llm_base import OutputLessToolCallLLM
from ...llm import MessageHistory, ModelBase, SystemMessage, UserMessage
from .easy_usage_wrappers.structured_llm import structured_llm
from ...interaction.call import call
from pydantic import BaseModel
from abc import ABC


class StructuredToolCallLLM(OutputLessToolCallLLM[str], ABC):

    def __init__(
        self,
        message_history: MessageHistory,
        llm_model: ModelBase,
        output_model: BaseModel,
    ):

        super().__init__(message_history, llm_model)
        system_structured = SystemMessage(
            "You are a structured LLM that can convert the response into a structured output."
        )
        self.structured_resp_node = structured_llm(output_model, system_message=system_structured, model=self.model)

    def return_output(self) -> BaseModel:
        # Return the structured output or raise the exception if it was an error
        if isinstance(self.structured_output, Exception):
            raise self.structured_output
        return self.structured_output
