from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel

from requestcompletion.exceptions.node_creation.validation import (
    check_classmethod,
    check_schema,
)

from ... import context
from ...exceptions import LLMError
from ...llm import MessageHistory, ModelBase
from ._llm_base import LLMBase

_TOutput = TypeVar("_TOutput", bound=BaseModel)


class StructuredLLM(LLMBase[_TOutput], ABC):
    # TODO: allow for more general (non-pydantic) outputs

    def __init_subclass__(cls):
        super().__init_subclass__()
        if "schema" in cls.__dict__ and not getattr(cls, "__abstractmethods__", False):
            method = cls.__dict__["schema"]
            check_classmethod(method, "schema")
            check_schema(method, cls)

    @classmethod
    @abstractmethod
    def schema(cls) -> Type[_TOutput]: ...

    def __init__(
        self, message_history: MessageHistory, llm_model: ModelBase | None = None
    ):
        """Creates a new instance of the StructuredlLLM class

        Args:
            message_history (MessageHistory): The message history to use for the LLM.
            llm_model (ModelBase | None, optional): The LLM model to use. Defaults to None.

        """
        super().__init__(llm_model=llm_model, message_history=message_history)

    @classmethod
    def pretty_name(cls) -> str:
        return cls.schema().__name__

    async def invoke(self) -> _TOutput:
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response

        Returns:
            (StructuredlLLM.Output): The response message from the llm model
        """

        returned_mess = await self.llm_model.astructured(
            self.message_hist, schema=self.schema()
        )

        self.message_hist.append(returned_mess.message)

        if returned_mess.message.role == "assistant":
            cont = returned_mess.message.content
            if cont is None:
                raise LLMError(
                    reason="ModelLLM returned None content",
                    message_history=self.message_hist,
                )
            if isinstance(cont, self.schema()):
                if (key := self.return_into()) is not None:
                    context.put(key, self.format_for_context(cont))
                    return self.format_for_return(cont)
                return cont
            raise LLMError(
                reason="The LLM returned content does not match the expected return type",
                message_history=self.message_hist,
            )

        raise LLMError(
            reason="ModelLLM returned an unexpected message type.",
            message_history=self.message_hist,
        )
