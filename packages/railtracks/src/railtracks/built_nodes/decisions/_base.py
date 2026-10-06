"""The System One model base, still emitting ``decision.*`` events.

Moves into ``railtracks.classifiers.model`` once emission moves to the invoker.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, TypeVar

from railtracks.classifiers.model import DecisionReply
from railtracks.classifiers.pricing import decision_cost
from railtracks.classifiers.response import DecisionResponse
from railtracks.classifiers.schema import DecisionSchema, DecisionState
from railtracks.context.central import get_current_scope, is_context_active
from railtracks.events._resolve import has_enclosing_node
from railtracks.events.decision import (
    DecisionFailureEvent,
    DecisionInvocationEvent,
    DecisionResponseEvent,
)
from railtracks.events.send import emit
from railtracks.exceptions import (
    DecisionRateLimitError,
    DecisionServerError,
    DecisionTimeoutError,
)
from railtracks.llm._exceptions import RetryError
from railtracks.llm.retries import RetryApproach

_TSchema = TypeVar("_TSchema", bound=DecisionSchema)
_TVendorSchema = TypeVar("_TVendorSchema", bound=DecisionSchema)

RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    DecisionRateLimitError,
    DecisionServerError,
    DecisionTimeoutError,
)


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
    def _describe_questions(self, schema: type[_TSchema]) -> dict[str, Any]:
        """``schema``'s questions as plain JSON, for the invocation event."""

    async def _ask(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionResponse[_TSchema]:
        # outside a node (a plain script, or a Session body) there is no parent to
        # resolve, and emitting would only log an error
        observed = is_context_active() and has_enclosing_node(get_current_scope())
        decision_id = str(uuid.uuid4())
        if observed:
            await emit(
                DecisionInvocationEvent(
                    decision_id=decision_id,
                    model_name=self.model_name,
                    api_base=self.api_base,
                    state=state,
                    questions=self._describe_questions(schema),
                )
            )

        start = time.perf_counter()
        try:
            reply = await self._send_with_retries(state, schema)
        except Exception as e:
            if observed:
                await emit(
                    DecisionFailureEvent.from_exception(
                        e, decision_id=decision_id, model_name=self.model_name
                    )
                )
            raise
        latency = time.perf_counter() - start

        response = DecisionResponse(
            structured=reply.structured,
            model_name=reply.reported_model_name or self.model_name,
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
        if observed:
            await emit(
                DecisionResponseEvent(
                    decision_id=decision_id,
                    model_name=self.model_name,
                    reported_model_name=reply.reported_model_name,
                    provider=reply.provider,
                    answers=response.structured.encode(),
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    total_cost=response.cost,
                    latency=latency,
                )
            )
        return response

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
