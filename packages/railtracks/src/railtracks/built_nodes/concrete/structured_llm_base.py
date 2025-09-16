import asyncio
from abc import ABC
from typing import Generic, TypeVar

from pydantic import BaseModel

import railtracks.context as context
from railtracks.exceptions import LLMError
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
        """Creates a new instance of the StructuredlLLM class

        Args:
            user_input (MessageHistory | UserMessage | str | list[Message]): The input to use for the LLM. Can be a MessageHistory object, a UserMessage object, or a string.
                If a string is provided, it will be converted to a MessageHistory with a UserMessage.
                If a UserMessage is provided, it will be converted to a MessageHistory.
            llm_model (ModelBase | None, optional): The LLM model to use. Defaults to None.

        """
        super().__init__(llm=llm, user_input=user_input)

    @classmethod
    def name(cls) -> str:
        return f"Structured LLM ({cls.output_schema().__name__})"

    async def invoke(self) -> StructuredResponse[_TOutput]:
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response

        Returns:
            (StructuredlLLM.Output): The response message from the llm model
        """

        returned_mess = await asyncio.to_thread(
            self.llm_model.structured, self.message_hist, schema=self.output_schema()
        )

        self.message_hist.append(returned_mess.message)

        if returned_mess.message.role == "assistant":
            cont = returned_mess.message.content
            if cont is None:
                raise LLMError(
                    reason="ModelLLM returned None content",
                    message_history=self.message_hist,
                )
            if isinstance(cont, self.output_schema()):
                if (key := self.return_into()) is not None:
                    context.put(key, self.format_for_context(cont))
                    return self.format_for_return(cont)
                return self.return_output()
            raise LLMError(
                reason="The LLM returned content does not match the expected return type",
                message_history=self.message_hist,
            )

        raise LLMError(
            reason="ModelLLM returned an unexpected message type.",
            message_history=self.message_hist,
        )
