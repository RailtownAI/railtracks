import asyncio
from abc import ABC
from typing import Generator, Generic, TypeVar

from pydantic import BaseModel

from railtracks.llm import Message, MessageHistory, ModelBase, UserMessage
from railtracks.validation.node_creation.validation import (
    check_classmethod,
    check_schema,
)

from ._llm_base import LLMBase, StructuredOutputMixIn
from .response import StructuredResponse

_TOutput = TypeVar("_TOutput", bound=BaseModel)


# note the ordering here does matter, the t
class StructuredLLM(
    StructuredOutputMixIn[_TOutput],
    LLMBase[StructuredResponse[_TOutput]],
    ABC,
    Generic[_TOutput],
):
    """Creates a new instance of the StructuredlLLM class

    Args:
        user_input (MessageHistory | UserMessage | str | list[Message]): The input to use for the LLM. Can be a MessageHistory object, a UserMessage object, or a string.
            If a string is provided, it will be converted to a MessageHistory with a UserMessage.
            If a UserMessage is provided, it will be converted to a MessageHistory.
        llm_model (ModelBase | None, optional): The LLM model to use. Defaults to None.

    """

    # TODO: allow for more general (non-pydantic) outputs

    def __init_subclass__(cls):
        super().__init_subclass__()
        if "output_schema" in cls.__dict__ and not getattr(
            cls, "__abstractmethods__", False
        ):
            method = cls.__dict__["output_schema"]
            check_classmethod(method, "output_schema")
            check_schema(method, cls)

    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
        llm: ModelBase | None = None,
    ):
        super().__init__(llm=llm, user_input=user_input)

    @classmethod
    def name(cls) -> str:
        return f"Structured LLM ({cls.output_schema().__name__})"

    async def invoke(self):
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response

        Returns:
            (StructuredlLLM.Output): The response message from the llm model
        """

        returned_mess = await asyncio.to_thread(
            self.llm_model.structured, self.message_hist, schema=self.output_schema()
        )

        if isinstance(returned_mess, Generator):
            return self._gen_wrapper(returned_mess)
        else:
            self._handle_output(returned_mess.message)
            return self.return_output(returned_mess.message)

    def _handle_output(self, output: Message):
        assert isinstance(output.content, self.output_schema())
        super()._handle_output(output)
