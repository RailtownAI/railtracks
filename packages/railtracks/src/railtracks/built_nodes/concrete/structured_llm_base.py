import asyncio
from abc import ABC
from typing import Generic, TypeVar

from pydantic import BaseModel

from railtracks.exceptions.errors import LLMError
from railtracks.llm import Message, MessageHistory, ModelBase, UserMessage
from railtracks.validation.node_creation.validation import (
    check_classmethod,
    check_schema,
)

from ._llm_base import LLMBase, StructuredOutputMixIn
from .response import StructuredResponse

_TOutput = TypeVar("_TOutput", bound=StructuredResponse)
_T = TypeVar("_T")
_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)


class StructuredLLMBase(
    StructuredOutputMixIn[_TBaseModel],
    LLMBase[_T, StructuredResponse[_TBaseModel]],
    ABC,
    Generic[_T, _TBaseModel],
):
    """
    Python typing doesn't work great, so please ensure that you fit the following requirements when defining generics:
    - _T is the final output type of the invoke method
    - _TBaseModel is a subclass of pydantic.BaseModel that defines the schema for the structured output

    """

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

    def _handle_output(self, output: Message):
        if not isinstance(output.content, self.output_schema()):
            raise LLMError(
                f"Output from LLM is not of the correct type. Got {type(output.content)} instead of {self.output_schema()}."
            )
        super()._handle_output(output)


class StructuredLLM(
    StructuredLLMBase[StructuredResponse[_TBaseModel], _TBaseModel],
    ABC,
    Generic[_TBaseModel],
):
    """Creates a new instance of the StructuredlLLM class

    Args:
        user_input (MessageHistory | UserMessage | str | list[Message]): The input to use for the LLM. Can be a MessageHistory object, a UserMessage object, or a string.
            If a string is provided, it will be converted to a MessageHistory with a UserMessage.
            If a UserMessage is provided, it will be converted to a MessageHistory.
        llm_model (ModelBase | None, optional): The LLM model to use. Defaults to None.

    """

    # TODO: allow for more general (non-pydantic) outputs

    async def invoke(self):
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response

        Returns:
            (StructuredlLLM.Output): The response message from the llm model
        """
        context = self._pre_invoke(self.message_hist)
        self.message_hist = context

        returned_mess = await asyncio.to_thread(
            self.llm_model.structured, self.message_hist, schema=self.output_schema()
        )

        returned_mess = self._post_invoke(self.message_hist, returned_mess)

        self._handle_output(returned_mess.message)
        return self.return_output(returned_mess.message)
