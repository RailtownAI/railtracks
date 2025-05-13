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
            "You are a structured LLM tasked with extracting structured information from the conversation history of another LLM.\n",
            "The input will be the full message history (including system, user, tool, and assistant messages) from a prior LLM interaction.",
            "Your job is to analyze this history and produce a structured response according to a specified format.\n",
            "Ensure the output is clean, valid, and matches the structure and schema defined. If certain fields cannot be confidently filled based on the conversation", 
            "return None\n",
            "Do not summarize, speculate, or reinterpret the original intent—only extract information that is directly supported by the conversation content.\n"
            "Respond only with the structured output in the specified format."
        )
        self.structured_resp_node = structured_llm(output_model, system_message=system_structured, model=self.model)

    def return_output(self) -> BaseModel:
        # Return the structured output or raise the exception if it was an error
        if isinstance(self.structured_output, Exception):
            raise self.structured_output
        return self.structured_output