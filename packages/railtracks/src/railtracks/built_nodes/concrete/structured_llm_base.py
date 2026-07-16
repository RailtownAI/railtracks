from __future__ import annotations

import asyncio
from abc import ABC
from typing import Generic, TypeVar

from pydantic import BaseModel

from railtracks.exceptions.errors import LLMError
from railtracks.llm import Message, MessageHistory, ModelBase, UserMessage
from railtracks.llm.response import Response
from railtracks.validation.node_creation.validation import (
    check_classmethod,
    check_schema,
)

from ._llm_base import LLMBase, StructuredOutputMixIn
from .response import StructuredResponse

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)


class StructuredLLMBase(
    StructuredOutputMixIn[_TBaseModel],
    LLMBase[StructuredResponse[_TBaseModel]],
    ABC,
    Generic[_TBaseModel],
):
    """
    Base class for LLM nodes returning structured (pydantic) output.

    Generics:
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
    StructuredLLMBase[_TBaseModel],
    ABC,
    Generic[_TBaseModel],
):
    """Creates a new instance of the StructuredlLLM class

    Streaming: when invoked through `rt.astream` / `Flow.astream`, the
    raw JSON tokens of the structured response are streamed chunk-by-chunk; the final returned
    `StructuredResponse` is parsed and validated once the stream completes. In a regular
    `rt.call` the model is invoked buffered.

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

        if self._should_stream():
            returned_mess = await self._stream_model_response(
                self.llm_model.astream_structured(
                    self.message_hist, schema=self.output_schema()
                )
            )
        else:
            returned_mess = await asyncio.to_thread(self._buffered_structured)

        returned_mess = self._post_invoke(self.message_hist, returned_mess)

        self._handle_output(returned_mess.message)
        return self.return_output(returned_mess.message)

    def _buffered_structured(self) -> Response:
        """Runs a regular (non-streaming) structured call, draining legacy stream=True generators."""
        return self._collect_streamed_response(
            self.llm_model.structured(self.message_hist, schema=self.output_schema())
        )
