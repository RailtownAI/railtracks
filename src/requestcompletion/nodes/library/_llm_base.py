from __future__ import annotations

import warnings
from abc import ABC
from copy import deepcopy
from typing import Any, Generic, TypeVar

from typing_extensions import Self

import requestcompletion.llm as llm
from requestcompletion.exceptions.node_invocation.validation import (
    check_llm_model,
    check_message_history,
)
from requestcompletion.llm.message import SystemMessage
from requestcompletion.llm.response import Response
from requestcompletion.nodes.nodes import Node

from ...exceptions.errors import NodeInvocationError
from ...exceptions.messages.exception_messages import get_message
from ...prompts.prompt import inject_context

_T = TypeVar("_T")


class RequestDetails:
    """
    A named tuple to store details of each LLM request.
    """

    def __init__(
        self,
        message_input: llm.MessageHistory,
        output: llm.Message | None,
        model_name: str | None,
        model_provider: str | None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_cost: float | None = None,
        system_fingerprint: str | None = None,
    ):
        self.input = message_input
        self.output = output
        self.model_name = model_name
        self.model_provider = model_provider
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_cost = total_cost
        self.system_fingerprint = system_fingerprint

    def __repr__(self):
        return f"RequestDetails(model_name={self.model_name}, model_provider={self.model_provider}, input={self.input}, output={self.output})"


class LLMBase(Node[_T], ABC, Generic[_T]):
    """
    A basic LLM base class that encapsulates the attaching of an LLM model and message history object.

    The main functionality of the class is contained within the attachment of pre and post hooks to the model so we can
    store debugging details that will allow us to determine token usage.

    """

    @classmethod
    def _verify_message_history(cls, message_history: llm.MessageHistory):
        """Verify the message history is valid for this LLM."""
        check_message_history(message_history, cls.system_message())

    @classmethod
    def _verify_llm_model(cls, llm_model: llm.ModelBase):
        """Verify the llm model is valid for this LLM."""
        check_llm_model(llm_model)

    @classmethod
    def get_llm_model(cls) -> llm.ModelBase | None:
        return None

    @classmethod
    def system_message(cls) -> SystemMessage | str | None:
        return None

    def __init__(
        self,
        message_history: llm.MessageHistory,
        llm_model: llm.ModelBase | None = None,
    ):
        super().__init__()

        message_history_copy = deepcopy(
            message_history
        )  # Ensure we don't modify the original message history
        self._verify_message_history(message_history_copy)

        if self.system_message() is not None:
            if not isinstance(self.system_message(), (SystemMessage, str)):
                raise NodeInvocationError(
                    message=get_message("INVALID_SYSTEM_MESSAGE_MSG"),
                    fatal=True,
                )
            if len([x for x in message_history_copy if x.role == "system"]) > 0:
                warnings.warn(
                    "System message was passed in message history and defined as a method. We will use the method definition."
                )
                message_history_copy = [
                    x for x in message_history_copy if x.role != "system"
                ]
            message_history_copy.insert(
                0,
                SystemMessage(self.system_message())
                if isinstance(self.system_message(), str)
                else self.system_message(),
            )

        if self.get_llm_model() is not None:
            if llm_model is not None:
                warnings.warn(
                    "You have provided an llm model as a parameter and as a class variable. We will use the parameter."
                )
            else:
                llm_model = self.get_llm_model()

        self._verify_llm_model(llm_model)
        self.llm_model = llm_model

        self.message_hist = message_history_copy

        self._details["llm_details"] = []

        self._attach_llm_hooks()

    def _attach_llm_hooks(self):
        """Attach pre and post hooks to the llm model."""
        self.llm_model.add_pre_hook(self._pre_llm_hook)
        self.llm_model.add_post_hook(self._post_llm_hook)
        self.llm_model.add_exception_hook(self._exception_llm_hook)

    def _detach_llm_hooks(self):
        """Detach pre and post hooks from the llm model."""
        self.llm_model.remove_pre_hooks()
        self.llm_model.remove_post_hooks()

    def _pre_llm_hook(self, message_history: llm.MessageHistory) -> llm.MessageHistory:
        """Hook to modify messages before sending them to the llm model."""
        return inject_context(message_history)

    def _post_llm_hook(self, message_history: llm.MessageHistory, response: Response):
        """Hook to store the response details after invoking the llm model."""
        self._details["llm_details"].append(
            RequestDetails(
                message_input=deepcopy(message_history),
                output=deepcopy(response.message),
                model_name=response.message_info.model_name
                if response.message_info.model_name is not None
                else self.llm_model.model_name(),
                model_provider=self.llm_model.model_type(),
                input_tokens=response.message_info.input_tokens,
                output_tokens=response.message_info.output_tokens,
                total_cost=response.message_info.total_cost,
                system_fingerprint=response.message_info.system_fingerprint,
            )
        )

        return response

    def _exception_llm_hook(
        self, message_history: llm.MessageHistory, exception: Exception
    ):
        """Hook to store the response details after exception was thrown during llm model invocation"""
        self._details["llm_details"].append(
            RequestDetails(
                message_input=deepcopy(message_history),
                output=None,
                model_name=self.llm_model.model_name(),
                model_provider=self.llm_model.model_type(),
            )
        )
        raise exception

    def return_into(self) -> str | None:
        """
        Return the name of the variable to return the result into. This method can be overridden by subclasses to
        customize the return variable name. By default, it returns None.

        Returns
        -------
        str
            The name of the variable to return the result into.
        """
        return None

    def format_for_return(self, result: _T) -> Any:
        """
        Format the result for return when return_into is provided. This method can be overridden by subclasses to
        customize the return format. By default, it returns None.

        Parameters
        ----------
        result : Any
            The result to format.

        Returns
        -------
        Any
            The formatted result.
        """
        return None

    def format_for_context(self, result: _T) -> Any:
        """
        Format the result for context when return_into is provided. This method can be overridden by subclasses to
        customize the context format. By default, it returns the result as is.

        Parameters
        ----------
        result : Any
            The result to format.

        Returns
        -------
        Any
            The formatted result.
        """
        return result

    def safe_copy(self) -> Self:
        new_instance: LLMBase = super().safe_copy()  # noqa: Type checking broken.

        # This has got to be one of the weirdest things I've seen working with python
        # basically if we don't reattach the hooks, the `self` inserted into the model hooks will be the old memory address
        # so those updates will go to the old instance instead of the new one.
        new_instance._detach_llm_hooks()
        new_instance._attach_llm_hooks()
        # now that we have reattached the correct memory address to the llm the hooks will update properly.

        return new_instance
