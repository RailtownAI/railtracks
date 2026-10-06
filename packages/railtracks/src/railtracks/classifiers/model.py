"""The vendor-neutral System One model client base.

``DecisionModel.aask`` times the call, retries transient failures and prices the
result. It records nothing: emitting ``decision.*`` events is the job of the
``decision_node`` invoker, just as only ``ModelInvoker`` records chat-model calls.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, TypeVar

from railtracks.exceptions import (
    DecisionRateLimitError,
    DecisionServerError,
    DecisionTimeoutError,
)
from railtracks.llm._exceptions import RetryError
from railtracks.llm.retries import RetryApproach

from .pricing import decision_cost
from .response import DecisionResponse
from .schema import DecisionSchema, DecisionState

_TSchema = TypeVar("_TSchema", bound=DecisionSchema)
_TVendorSchema = TypeVar("_TVendorSchema", bound=DecisionSchema)

RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    DecisionRateLimitError,
    DecisionServerError,
    DecisionTimeoutError,
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

    def __init__(
        self,
        model_name: str,
        *,
        api_base: str,
        retry_approach: RetryApproach | None = None,
    ) -> None:
        self.model_name = model_name
        self.api_base = api_base
        self.retry_approach = retry_approach

    @abstractmethod
    async def aask(
        self, state: DecisionState, schema: type[_TVendorSchema]
    ) -> DecisionResponse[_TVendorSchema]:
        """Answer every question in ``schema`` about ``state`` in one request."""

    @abstractmethod
    async def _send(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
        """Make one request, raising a ``DecisionModelError`` on failure."""

    @abstractmethod
    def _pricing_keys(self) -> list[str]:
        """The ``litellm.model_cost`` keys to try for this model, in order."""

    @abstractmethod
    def describe_questions(self, schema: type[_TSchema]) -> dict[str, Any]:
        """``schema``'s questions as plain JSON, as the request would carry them."""

    async def _ask(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionResponse[_TSchema]:
        start = time.perf_counter()
        reply = await self._send_with_retries(state, schema)
        latency = time.perf_counter() - start
        return DecisionResponse(
            structured=reply.structured,
            model_name=reply.reported_model_name or self.model_name,
            requested_model_name=self.model_name,
            provider=reply.provider,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            latency=latency,
            # what the host billed, when it says; else the LiteLLM catalog price
            cost=reply.reported_cost
            if reply.reported_cost is not None
            else decision_cost(
                self._pricing_keys(), reply.input_tokens, reply.output_tokens
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
            # surface the decision error itself, not the LLM-flavoured RetryError
            raise e.exception_list[-1] from e
