from __future__ import annotations

from abc import ABC
from copy import deepcopy
from typing import Generic, TypeVar

from typing_extensions import Self

import requestcompletion.llm as llm
from requestcompletion.exceptions.node_invocation.validation import (
    check_message_history,
)
from requestcompletion.llm.response import Response
from requestcompletion.nodes.nodes import Node

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

    def __init__(self, model: llm.ModelBase, message_history: llm.MessageHistory):
        super().__init__()
        self.model = model
        check_message_history(
            message_history
        )  # raises NodeInvocationError if any of the checks fail
        self.message_hist = deepcopy(message_history)

        self._details["llm_details"] = []

        self._attach_llm_hooks()

    def _attach_llm_hooks(self):
        """Attach pre and post hooks to the model."""
        self.model.add_pre_hook(self._pre_llm_hook)
        self.model.add_post_hook(self._post_llm_hook)
        self.model.add_exception_hook(self._exception_llm_hook)

    def _detach_llm_hooks(self):
        """Detach pre and post hooks from the model."""
        self.model.remove_pre_hooks()
        self.model.remove_post_hooks()

    def _pre_llm_hook(self, message_history: llm.MessageHistory) -> llm.MessageHistory:
        """Hook to modify messages before sending them to the model."""
        return inject_context(message_history)

    def _post_llm_hook(self, message_history: llm.MessageHistory, response: Response):
        """Hook to store the response details after invoking the model."""
        self._details["llm_details"].append(
            RequestDetails(
                message_input=deepcopy(message_history),
                output=deepcopy(response.message),
                model_name=response.message_info.model_name
                if response.message_info.model_name is not None
                else self.model.model_name(),
                model_provider=self.model.model_type(),
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
        """Hook to store the response details after exception was thrown during model invocation"""
        self._details["llm_details"].append(
            RequestDetails(
                message_input=deepcopy(message_history),
                output=None,
                model_name=self.model.model_name(),
                model_provider=self.model.model_type(),
            )
        )
        raise exception

    def safe_copy(self) -> Self:
        new_instance: LLMBase = super().safe_copy()  # noqa: Type checking broken.

        # This has got to be one of the weirdest things I've seen working with python
        # basically if we don't reattach the hooks, the `self` inserted into the model hooks will be the old memory address
        # so those updates will go to the old instance instead of the new one.
        new_instance._detach_llm_hooks()
        new_instance._attach_llm_hooks()
        # now that we have reattached the correct memory address to the llm the hooks will update properly.

        return new_instance
