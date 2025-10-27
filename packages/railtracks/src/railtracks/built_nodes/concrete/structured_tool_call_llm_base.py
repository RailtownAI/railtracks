from abc import ABC
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

from railtracks.exceptions.errors import LLMError
from railtracks.interaction import call
from railtracks.llm import (
    AssistantMessage,
    Message,
    MessageHistory,
    ModelBase,
    UserMessage,
)

from ._llm_base import StructuredOutputMixIn
from ._tool_call_base import (
    OutputLessToolCallLLM,
)
from .response import StructuredResponse

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)
_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class StructuredToolCallLLM(
    StructuredOutputMixIn[_TBaseModel],
    OutputLessToolCallLLM[StructuredResponse[_TBaseModel]],
    ABC,
    Generic[_TBaseModel],
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
            "Ensure the output is clean, valid, and matches the structure and output_schema defined. If certain fields cannot be confidently filled based on the conversation"
            "return None\n"
            "Do not summarize, speculate, or reinterpret the original intent—only extract information that is directly supported by the conversation content.\n"
            "Respond only with the structured output in the specified format."
        )

        has_abstract_methods = any(
            getattr(getattr(cls, name, None), "__isabstractmethod__", False)
            for name in dir(cls)
        )

        from ..easy_usage_wrappers.helpers import structured_llm

        # we only want to verify the output_schema is the class is not abstract
        if not has_abstract_methods:
            cls.structured_resp_node = structured_llm(
                cls.output_schema(),
                system_message=system_structured,
                llm=cls.get_llm(),
            )

        super().__init_subclass__()

    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
        llm: ModelBase[Literal[False]] | None = None,
        max_tool_calls: int | None = None,
    ):
        # as of right now we do not support streaming with structured tool calls.
        if llm is not None and llm.stream:
            raise ValueError("StructuredToolCallLLM does not support streaming.")

        super().__init__(user_input=user_input, llm=llm, max_tool_calls=max_tool_calls)
        self.structured_output: _TBaseModel | Exception | None = None

    async def invoke(self):
        await self._handle_tool_calls()

        try:
            response = await call(
                self.structured_resp_node,
                user_input=MessageHistory(
                    [UserMessage(str(self.message_hist), inject_prompt=False)]
                ),
                llm=self.llm_model,
            )

            structured_output = response
        except Exception as e:
            # the original exception will be presented with our wrapped one.
            raise LLMError(
                reason="Failed to parse assistant response into structured output.",
                message_history=self.message_hist,
            ) from e

        return self._handle_structured_output(structured_output)

    def _handle_structured_output(self, output: StructuredResponse[_TBaseModel]):
        structured = output.structured

        assert isinstance(structured, self.output_schema())
        last_message = AssistantMessage(content=structured)
        self.message_hist.pop()
        self.message_hist.append(last_message)
        return self.return_output(last_message)
