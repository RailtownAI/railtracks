from abc import ABC, abstractmethod
from typing import Generic, Type, TypeVar

from pydantic import BaseModel

from requestcompletion.exceptions.errors import LLMError
from requestcompletion.llm import AssistantMessage, MessageHistory, SystemMessage
from requestcompletion.nodes.library.tool_calling_llms._structured_base import OutputLessStructuredToolCallLLM

from ..easy_usage_wrappers.structured_llm import structured_llm
from ._base import OutputLessToolCallLLM

_TOutput = TypeVar("_TOutput", bound=BaseModel)


class StructuredToolCallLLM(OutputLessStructuredToolCallLLM[_TOutput, _TOutput], ABC, Generic[_TOutput]):



    def return_output(self) -> _TOutput:
        # Return the structured output or raise the exception if it was an error
        if self.structured_output is None:
            raise LLMError("Structured output is None, a unknown error occurred.")
        
        if isinstance(self.structured_output, Exception):
            raise self.structured_output from self.structured_output
            
        return self.structured_output
    
