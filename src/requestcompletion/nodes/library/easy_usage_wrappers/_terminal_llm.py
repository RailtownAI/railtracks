import warnings
from typing import Any, TypeVar, Generic
from pydantic import BaseModel
from inspect import isclass, isfunction
from abc import ABC, abstractmethod
from requestcompletion.llm import (
    MessageHistory,
    ModelBase,
)
from requestcompletion.nodes.library import structured_llm
from requestcompletion.nodes.library.function import from_function
from requestcompletion.run import call
from requestcompletion.nodes.library.easy_usage_wrappers.easy_base import EasyBase
from requestcompletion.nodes.nodes import Node
from requestcompletion.exceptions import NodeCreationError, LLMError
from requestcompletion.exceptions.node_invocation.validation import check_max_tool_calls
from requestcompletion.exceptions.node_invocation.validation import check_model
import requestcompletion as rc

_T = TypeVar("_T")


class TerminalBase(EasyBase[str], ABC):
    """A simple LLM nodes that takes in a message and returns a response. It is the simplest of all llms."""

    def __init__(self, message_history: MessageHistory, llm_model: ModelBase | None = None):
        """Creates a new instance of the TerminalLLM class

        Args:

        """
        if llm_model is not None:
            if self.__class__._model is not None:
                warnings.warn(
                    "You have provided a model as a parameter and as a class variable. We will use the parameter."
                )
        else:
            check_model(
                self.__class__._model
            )  # raises NodeInvocationError if any of the checks fail
            llm_model = self.__class__._model

        super().__init__(llm_model=llm_model, message_history=message_history)

    async def invoke(self) -> str | None:
        """Makes a call containing the inputted message and system prompt to the model and returns the response

        Returns:
            (TerminalLLM.Output): The response message from the model
        """
        try:
            returned_mess = self.model.chat(self.message_hist)
        except Exception as e:
            raise LLMError(
                reason=f"Exception during model chat: {str(e)}",
                message_history=self.message_hist,
            )

        self.message_hist.append(returned_mess.message)
        if returned_mess.message.role == "assistant":
            cont = returned_mess.message.content
            if cont is None:
                raise LLMError(
                    reason="ModelLLM returned None content",
                    message_history=self.message_hist,
                )
            return cont

        raise LLMError(
            reason="ModelLLM returned an unexpected message type.",
            message_history=self.message_hist,
        )