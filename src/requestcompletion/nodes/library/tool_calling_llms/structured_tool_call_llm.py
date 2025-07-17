from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel

from ..easy_usage_wrappers.structured_llm import structured_llm
from ._base import OutputLessToolCallLLM

_TOutput = TypeVar("_TOutput", bound=BaseModel)


class StructuredToolCallLLM(OutputLessToolCallLLM[str], ABC):
    def __init_subclass__(cls):
        super().__init_subclass__()
        system_structured = (
            "You are a structured LLM tasked with extracting structured information from the conversation history of another LLM.\n"
            "The input will be the full message history (including system, user, tool, and assistant messages) from a prior LLM interaction."
            "Your job is to analyze this history and produce a structured response according to a specified format.\n"
            "Ensure the output is clean, valid, and matches the structure and schema defined. If certain fields cannot be confidently filled based on the conversation"
            "return None\n"
            "Do not summarize, speculate, or reinterpret the original intent—only extract information that is directly supported by the conversation content.\n"
            "Respond only with the structured output in the specified format."
        )

        cls.structured_resp_node = structured_llm(
            cls.output_model(),
            system_message=system_structured,
            llm_model=cls.get_llm_model,
        )

    @classmethod
    @abstractmethod
    def output_model(cls) -> Type[_TOutput]: ...

    def return_output(self) -> BaseModel:
        # Return the structured output or raise the exception if it was an error
        if isinstance(self.structured_output, Exception):
            raise self.structured_output from self.structured_output
        return self.structured_output
