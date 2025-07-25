from abc import ABC, abstractmethod
from typing import Generic, Type, TypeVar

from pydantic import BaseModel

import railtracks.context as context
from railtracks.exceptions.errors import LLMError
from railtracks.interaction.call import call
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import UserMessage
from railtracks.llm.model import ModelBase
from railtracks.nodes.library.easy_usage_wrappers.structured_llms.structured_llm import (
    structured_llm,
)
from railtracks.nodes.library.tool_calling_llms._base import (
    OutputLessToolCallLLM,
)

_TReturn = TypeVar("_TReturn")
_TOutput = TypeVar("_TOutput", bound=BaseModel)


class OutputLessStructuredToolCallLLM(
    OutputLessToolCallLLM[_TReturn], ABC, Generic[_TReturn, _TOutput]
):
    """
    A base class for structured tool call LLMs that do not return an output.
    This class is used to define the structure of the tool call and handle the
    structured output.
    """

    def __init_subclass__(cls):
        system_structured = (
            "You are a structured LLM tasked with extracting structured information from the conversation history of another LLM.\n"
            "The input will be the full message history (including system, user, tool, and assistant messages) from a prior LLM interaction."
            "Your job is to analyze this history and produce a structured response according to a specified format.\n"
            "Ensure the output is clean, valid, and matches the structure and schema defined. If certain fields cannot be confidently filled based on the conversation"
            "return None\n"
            "Do not summarize, speculate, or reinterpret the original intent—only extract information that is directly supported by the conversation content.\n"
            "Respond only with the structured output in the specified format."
        )

        has_abstract_methods = any(
            getattr(getattr(cls, name, None), "__isabstractmethod__", False)
            for name in dir(cls)
        )

        # we only want to verify the schema is the class is not abstract
        if not has_abstract_methods:
            cls.structured_resp_node = structured_llm(
                cls.schema(),
                system_message=system_structured,
                llm_model=cls.get_llm_model,
            )

        super().__init_subclass__()

    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str,
        llm_model: ModelBase | None = None,
        max_tool_calls: int | None = None,
    ):
        super().__init__(user_input, llm_model, max_tool_calls)
        self.structured_output: _TOutput | Exception | None = None

    @classmethod
    @abstractmethod
    def schema(cls) -> Type[_TOutput]: ...

    async def invoke(self):
        await self._handle_tool_calls()

        try:
            self.structured_output = await call(
                self.structured_resp_node,
                user_input=MessageHistory(
                    [UserMessage(str(self.message_hist), inject_prompt=False)]
                ),
            )
        except Exception:
            # will be raised in the return_output method in StructuredToolCallLLM
            self.structured_output = LLMError(
                reason="Failed to parse assistant response into structured output.",
                message_history=self.message_hist,
            )

        if (key := self.return_into()) is not None:
            output = self.return_output()
            context.put(key, self.format_for_context(output))
            return self.format_for_return(output)

        return self.return_output()
