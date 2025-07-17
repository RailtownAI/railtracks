from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel

from requestcompletion.exceptions.node_creation.validation import (
    check_classmethod,
    check_output_model,
)

from ...exceptions import LLMError
from ...llm import MessageHistory, ModelBase
from ._llm_base import LLMBase

_TOutput = TypeVar("_TOutput", bound=BaseModel)


class StructuredLLM(LLMBase[_TOutput], ABC):
    # TODO: allow for more general (non-pydantic) outputs

    def __init_subclass__(cls):
        super().__init_subclass__()
        if "output_model" in cls.__dict__ and not getattr(
            cls, "__abstractmethods__", False
        ):
            method = cls.__dict__["output_model"]
            check_classmethod(method, "output_model")
            check_output_model(method, cls)

    @classmethod
    @abstractmethod
    def output_model(cls) -> Type[_TOutput]: ...

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
        return cls.output_model().__name__

    async def invoke(self) -> _TOutput:
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response

        Returns:
            (StructuredlLLM.Output): The response message from the llm model
        """

        returned_mess = await self.llm_model.astructured(
            self.message_hist, schema=self.output_model()
        )

        self.message_hist.append(returned_mess.message)

        if returned_mess.message.role == "assistant":
            cont = returned_mess.message.content
            if cont is None:
                raise LLMError(
                    reason="ModelLLM returned None content",
                    message_history=self.message_hist,
                )
            if isinstance(cont, self.output_model()):
                return cont
            raise LLMError(
                reason="The LLM returned content does not match the expected return type",
                message_history=self.message_hist,
            )

        raise LLMError(
            reason="ModelLLM returned an unexpected message type.",
            message_history=self.message_hist,
        )
