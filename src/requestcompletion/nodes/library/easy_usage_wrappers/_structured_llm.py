import asyncio
import warnings
from copy import deepcopy
from typing import Set, Type, Union, Literal, Dict, Any, Callable, TypeVar, Generic
from pydantic import BaseModel
from inspect import isclass, isfunction
from abc import ABC, abstractmethod
from requestcompletion.llm import (
    MessageHistory,
    SystemMessage,
    ModelBase,
)
from requestcompletion.nodes.library import structured_llm
from requestcompletion.nodes.library.function import from_function
from requestcompletion.run import call
from requestcompletion.nodes.library.easy_usage_wrappers.easy_base import EasyBase
from requestcompletion.nodes.nodes import Node
from requestcompletion.exceptions import NodeCreationError, LLMError
from requestcompletion.exceptions.node_invocation.validation import check_max_tool_calls
from requestcompletion.exceptions import NodeCreationError
from requestcompletion.exceptions.node_invocation.validation import check_model
import requestcompletion as rc

_T = TypeVar("_T")
_TOutput = TypeVar("_TOutput", bound=BaseModel)

class StructuredBase(EasyBase[_T], ABC, Generic[_T, _TOutput]):
    def __init_subclass__(
        cls,
        output_type: Literal["MessageHistory", "LastMessage"] = "LastMessage",
        output_model: BaseModel | None = None,
        **kwargs,
    ):
        has_abstract_methods = any(
        getattr(getattr(cls, name, None), '__isabstractmethod__', False)
        for name in dir(cls)
        )

        if not has_abstract_methods:
            cls._output_type = output_type
            cls._output_model = output_model

        super().__init_subclass__(**kwargs)

    def __init__(
        self,
        message_history: MessageHistory,
        llm_model: ModelBase | None = None,
    ):
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


        super().__init__(message_history=message_history, llm_model=llm_model)

    @classmethod
    def pretty_name(cls) -> str:
        if cls._pretty_name is None:
            return cls._output_model.__name__
        else:
            return cls._pretty_name

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
