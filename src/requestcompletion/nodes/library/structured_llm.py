from typing import TypeVar, Type
from copy import deepcopy
from ...llm import MessageHistory, ModelBase
from ..nodes import Node

from pydantic import BaseModel
from abc import ABC, abstractmethod

print("hello world")
_TOutput = TypeVar("_TOutput", bound=BaseModel)


class StructuredLLM(Node[_TOutput], ABC):
    # TODO: allow for more general (non-pydantic) outputs
    @classmethod
    @abstractmethod
    def output_model(cls) -> Type[_TOutput]: ...

    def __init__(self, message_history: MessageHistory, model: ModelBase):
        """Creates a new instance of the TerminalLLM class

        Args:

        """
        super().__init__()
        self.model = model
        self.message_hist = deepcopy(message_history)

    async def invoke(self) -> _TOutput:
        """Makes a call containing the inputted message and system prompt to the model and returns the response

        Returns:
            (TerminalLLM.Output): The response message from the model
        """

        returned_mess = self.model.structured(
            self.message_hist, schema=self.output_model()
        )

        self.message_hist.append(returned_mess.message)

        if returned_mess.message.role == "assistant":
            cont = returned_mess.message.content
            if cont is None:
                raise RuntimeError("ModelLLM returned None content")
            if isinstance(cont, self.output_model()):
                return cont
            raise RuntimeError(
                "The LLM returned content does not match the expected return type"
            )

        raise RuntimeError(
            "ModelLLM returned an unexpected message type.",
        )
