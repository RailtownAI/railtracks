"""The vendor-neutral System One model client base.

``DecisionModel.aask`` times the call, retries transient failures and prices the
result. It records nothing: emitting ``decision.*`` events is the job of the
``decision_node`` invoker, just as only ``ModelInvoker`` records chat-model calls.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, TypeVar, cast

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
from .schema import DecisionSchema, DecisionState

_TSchema = TypeVar("_TSchema", bound=DecisionSchema)
_TVendorSchema = TypeVar("_TVendorSchema", bound=DecisionSchema)

RETRYABLE_ERRORS: tuple[type[DecisionProviderError], ...] = (
    DecisionProviderRateLimitError,
    DecisionProviderTimeoutError,
    DecisionProviderConnectionError,
    DecisionProviderServerError,
)


@dataclass(frozen=True)
class DecisionReply(Generic[_TSchema]):
    """What a vendor's transport returns for one successful request."""

    structured: _TSchema
    reported_model_name: str | None
    provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    reported_cost: float | None
    raw: dict[str, Any]


class DecisionModel(ABC, Generic[_TVendorSchema]):
    """Base for a System One model client, generic in the vendor's schema base."""

    schema_base: ClassVar[type[DecisionSchema]]
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
    def api_base(self) -> str | None:
        """The base URL the next call goes to, or None if none is configured."""

    @abstractmethod
    async def aask(
        self, state: DecisionState, schema: type[_TVendorSchema]
    ) -> DecisionResponse[_TVendorSchema]:
        """Answer every question in ``schema`` about ``state`` in one request."""

    @abstractmethod
    async def _send(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
        """Make one request, raising a ``DecisionProviderError`` on failure."""

    @abstractmethod
    def _pricing_keys(self) -> list[str]:
        """The ``litellm.model_cost`` keys to try for this model, in order."""

    @abstractmethod
    def describe_questions(self, schema: type[_TSchema]) -> dict[str, Any]:
        """``schema``'s questions as plain JSON, as the request would carry them."""

    def _check_request(self, state: DecisionState, schema: type[_TSchema]) -> None:
        """Reject a request the host can't take, before any attempt. No-op by default."""

    async def _ask(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionResponse[_TSchema]:
        self._check_request(state, schema)
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
            # what the host billed, when it says; else the LiteLLM catalog price
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
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
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
        # the httpx root cause, which `last.__cause__` still holds.
        last.notes.append(f"Gave up after {attempts} attempts.")
        raise last
