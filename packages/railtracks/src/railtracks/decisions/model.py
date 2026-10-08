"""The vendor-neutral System One model client base.

``DecisionModel.aask`` times the call, retries transient failures and prices the
result. It records nothing: emitting ``decision.*`` events is the job of the
``decision_node`` invoker, just as only ``ModelInvoker`` records chat-model calls.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, cast

from railtracks.llm.retries import RetryApproach, RetryError

from ._exceptions import (
    DecisionProviderConnectionError,
    DecisionProviderError,
    DecisionProviderRateLimitError,
    DecisionProviderServerError,
    DecisionProviderTimeoutError,
)
from .pricing import decision_cost
from .response import DecisionResponse
from .schema import DecisionAnswers, DecisionSchema
from .state import DecisionInput

RETRYABLE_ERRORS: tuple[type[DecisionProviderError], ...] = (
    DecisionProviderRateLimitError,
    DecisionProviderTimeoutError,
    DecisionProviderConnectionError,
    DecisionProviderServerError,
)


@dataclass(frozen=True)
class DecisionReply:
    """What a vendor's transport returns for one successful request."""

    structured: DecisionAnswers
    reported_model_name: str | None
    provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    reported_cost: float | None
    raw: dict[str, Any]


class DecisionModel(ABC):
    """Base for a System One model client: answers any ``DecisionSchema``."""

    provider_name: str
    """Who serves the model; the response's ``provider`` when the host reports none."""
    bills_output_tokens: ClassVar[bool] = True
    """Whether catalog pricing should charge output tokens; False when the API bills
    input only (OpenAI's Decisions API) but the catalog lists chat prices."""

    def __init__(
        self, model_name: str, *, retry_approach: RetryApproach | None = None
    ) -> None:
        self.model_name = model_name
        self.retry_approach = retry_approach

    @property
    @abstractmethod
    def api_base(self) -> str:
        """The base URL the next call goes to."""

    @abstractmethod
    async def _send(
        self, state: DecisionInput, schema: DecisionSchema
    ) -> DecisionReply:
        """Make one request, raising a ``DecisionProviderError`` on failure."""

    @abstractmethod
    def _pricing_keys(self) -> list[str]:
        """The ``litellm.model_cost`` keys to try for this model, in order."""

    @abstractmethod
    def describe_questions(self, schema: DecisionSchema) -> dict[str, Any]:
        """``schema``'s questions as plain JSON, as the request would carry them."""

    async def aask(
        self, state: DecisionInput, schema: DecisionSchema
    ) -> DecisionResponse:
        """Answer every question in ``schema`` about ``state`` in one request.

        Args:
            state: What to judge: text, a JSON object or array (sent as JSON text), a
                ``DecisionState`` with image attachments, or a list of user messages.
                Images are accepted only where the provider takes them (OpenAI).
            schema: The ``DecisionSchema`` holding the questions.

        Returns:
            The answers (``DecisionAnswers``), with model, token, latency and cost
            metadata.

        Raises:
            DecisionProviderRefusalError: If the model declines any question.
            DecisionProviderError: If the call fails otherwise; the subclass says why.
        """
        start = time.perf_counter()
        reply = await self._send_with_retries(state, schema)
        latency = time.perf_counter() - start
        return DecisionResponse(
            structured=reply.structured,
            model_name=reply.reported_model_name or self.model_name,
            requested_model_name=self.model_name,
            provider=reply.provider or self.provider_name,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            latency=latency,
            # what litellm priced the call at, when it says; else the catalog price
            cost=reply.reported_cost
            if reply.reported_cost is not None
            else decision_cost(
                self._pricing_keys(),
                reply.input_tokens,
                reply.output_tokens if self.bills_output_tokens else None,
            ),
            raw=reply.raw,
        )

    async def _send_with_retries(
        self, state: DecisionInput, schema: DecisionSchema
    ) -> DecisionReply:
        if self.retry_approach is None:
            return await self._send(state, schema)
        try:
            return await self.retry_approach.acall_with_retry(
                lambda: self._send(state, schema), retry_on=RETRYABLE_ERRORS
            )
        except RetryError as e:
            attempts = len(e.exception_list)
            # retry_on admits only RETRYABLE_ERRORS, so every entry is one of ours
            last = cast(DecisionProviderError, e.exception_list[-1])
        # Raise the last provider error itself, outside the except block: chaining it
        # to the RetryError (whose own cause is this error) would make a cycle and hide
        # the litellm root cause, which `last.__cause__` still holds.
        last.notes.append(f"Gave up after {attempts} attempts.")
        raise last
