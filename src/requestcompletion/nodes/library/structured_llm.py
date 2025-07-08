from typing import TypeVar, Type

from ._llm_base import LLMBase
from ...llm import MessageHistory, ModelBase
from ...exceptions import LLMError
from pydantic import BaseModel
from abc import ABC, abstractmethod

_TOutput = TypeVar("_TOutput", bound=BaseModel)


class StructuredLLM(LLMBase[_TOutput], ABC):
    # TODO: allow for more general (non-pydantic) outputs
    @classmethod
    @abstractmethod
    def output_model(cls) -> Type[_TOutput]: ...

    def __init__(self, message_history: MessageHistory, model: ModelBase):
        """Creates a new instance of the TerminalLLM class

        Args:

        """
        super().__init__(model=model, message_history=message_history)

    async def invoke(self) -> _TOutput:
        """Makes a call containing the inputted message and system prompt to the model and returns the response

        Returns:
            (TerminalLLM.Output): The response message from the model
        """

        returned_mess = await self.model.astructured(
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
