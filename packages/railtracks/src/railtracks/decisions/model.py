"""``DecisionModel``: a System One model client, called through ``litellm.adecisions``.

The counterpart of ``llm/models/_litellm_wrapper.py``: litellm owns the provider's URL,
key lookup and wire translation; ``DecisionModel`` sends the OpenAI-shape request
(``transport/_wire.py``), retries litellm's transient exceptions, maps the one it ends
on to ``DecisionProviderError`` and reads usage, model and cost. A provider subclass
only sets class attributes.

It records nothing: emitting ``decision.*`` events is the job of the ``decision_node``
invoker, just as only ``ModelInvoker`` records chat-model calls.
"""

from __future__ import annotations

import dataclasses
import time
from typing import ClassVar, Union

import litellm
from litellm.types.decisions import DecisionsResponse, OpenAIDecisionResponse
from typing_extensions import TypeAlias

from railtracks.llm.retries import RetryApproach, RetryError

from ._exceptions import (
    DecisionProviderAuthenticationError,
    DecisionProviderError,
    DecisionProviderRateLimitError,
    DecisionProviderTimeoutError,
)
from .response import DecisionResponse
from .schema import DecisionSchema
from .state import DecisionInput
from .transport._client_cleanup import close_client_on_loop_shutdown
from .transport._wire import parse_response, questions_to_wire, to_input

# litellm prints a "Give Feedback / Get Help" banner on every mapped error without it
litellm.suppress_debug_info = True

LiteLLMDecisionResponse: TypeAlias = Union[OpenAIDecisionResponse, DecisionsResponse]
"""What ``litellm.adecisions`` returns."""

# Checked in order; any other exception propagates unchanged. litellm.Timeout is not
# a litellm.APIConnectionError, so it needs its own entry.
_LITELLM_ERRORS: tuple[
    tuple[tuple[type[Exception], ...], type[DecisionProviderError]], ...
] = (
    ((litellm.Timeout,), DecisionProviderTimeoutError),
    ((litellm.RateLimitError,), DecisionProviderRateLimitError),
    (
        (litellm.AuthenticationError, litellm.PermissionDeniedError),
        DecisionProviderAuthenticationError,
    ),
    (
        (
            litellm.APIConnectionError,
            litellm.APIError,
            litellm.APIResponseValidationError,
            litellm.BadGatewayError,
            litellm.BadRequestError,
            litellm.InternalServerError,
            litellm.NotFoundError,
            litellm.ServiceUnavailableError,
            litellm.UnprocessableEntityError,
        ),
        DecisionProviderError,
    ),
)


def _optional_cost(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


class DecisionModel:
    """A System One model client: answers any ``DecisionSchema`` through ``litellm.adecisions``.

    Create a provider subclass (``TypeSafeDecisions``, ``OpenRouterDecisions``,
    ``OpenAIDecisions``), not this base class.

    Attributes:
        provider_prefix: litellm's provider name, prefixed to the model name
            (``"typesafe/jev-latest"``).
        provider_name: Who serves the model: the response's ``provider``.
    """

    provider_prefix: ClassVar[str]
    provider_name: ClassVar[str]

    def __init__(
        self,
        model_name: str,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float = 30.0,
        retry_approach: RetryApproach | None = None,
    ) -> None:
        """Create a client. Nothing is sent, and no environment is read, until a call.

        Args:
            model_name: The model to ask, without the provider prefix.
            api_key: The API key. Defaults to the provider's environment variable,
                which litellm reads at call time.
            api_base: The server's base URL, passed to litellm as is. Defaults to
                litellm's own lookup (the provider's environment variable, then its
                default URL).
            timeout: Seconds to wait for each request.
            retry_approach: Retry strategy for litellm's transient errors (rate
                limits, timeouts, connection failures, 500 and 503). None (the
                default) makes one attempt, as for LLM providers.

        Raises:
            TypeError: If the class sets no ``provider_prefix`` or ``provider_name``.
        """
        missing = [
            name
            for name in ("provider_prefix", "provider_name")
            if not hasattr(self, name)
        ]
        if missing:
            raise TypeError(
                f"{type(self).__name__} sets no {' or '.join(missing)}; create a "
                "provider class such as TypeSafeDecisions instead."
            )
        self.model_name = model_name
        self.retry_approach = retry_approach
        self._api_key = api_key
        self._api_base = api_base
        self._timeout = timeout

    @property
    def litellm_model(self) -> str:
        """The model name litellm routes on: ``"<provider_prefix>/<model_name>"``."""
        return f"{self.provider_prefix}/{self.model_name}"

    async def aask(
        self, state: DecisionInput, schema: DecisionSchema
    ) -> DecisionResponse:
        """Answer every question in ``schema`` about ``state`` in one request.

        Args:
            state: What to judge: text, or a JSON object or array (sent as JSON
                text).
            schema: The ``DecisionSchema`` holding the questions.

        Returns:
            The answers (``DecisionAnswers``), with model, token, latency and cost
            metadata.

        Raises:
            DecisionProviderRefusalError: If the model declines any question.
            DecisionProviderError: If the call fails otherwise; a subclass for a
                timeout, rate limit or rejected key.
        """
        await close_client_on_loop_shutdown(self.provider_prefix)
        start = time.perf_counter()
        response = await self._adecisions(state, schema)
        latency = time.perf_counter() - start

        parsed = parse_response(
            response,
            schema,
            requested_model_name=self.model_name,
            provider=self.provider_name,
            latency=latency,
        )
        return dataclasses.replace(
            parsed, cost=self._cost(response, parsed.input_tokens)
        )

    def _cost(
        self, response: LiteLLMDecisionResponse, input_tokens: int | None
    ) -> float | None:
        """The call's cost in USD: litellm's ``response_cost``, or None when litellm
        could not price it. ``OpenAIDecisions`` overrides it to price input tokens only."""
        hidden = getattr(response, "_hidden_params", None) or {}
        return _optional_cost(hidden.get("response_cost"))

    async def _adecisions(
        self, state: DecisionInput, schema: DecisionSchema
    ) -> LiteLLMDecisionResponse:
        """One ``litellm.adecisions`` call, retried per ``retry_approach``."""

        async def adecisions() -> LiteLLMDecisionResponse:
            return await litellm.adecisions(
                model=self.litellm_model,
                input=to_input(state),
                questions=questions_to_wire(schema),
                api_key=self._api_key,
                api_base=self._api_base,
                timeout=self._timeout,
            )

        try:
            if self.retry_approach is None:
                return await adecisions()
            return await self.retry_approach.acall_with_retry(adecisions)
        except Exception as e:
            # classify once, by the attempt the retries ended on
            failure = e.exception_list[-1] if isinstance(e, RetryError) else e
            error = self._provider_error(failure)
            if error is None:
                raise
            if isinstance(e, RetryError):
                error.notes.append(f"Gave up after {len(e.exception_list)} attempts.")
            raise error from failure

    def _provider_error(self, error: Exception) -> DecisionProviderError | None:
        """The ``DecisionProviderError`` for a litellm exception; None for any other."""
        for litellm_types, provider_type in _LITELLM_ERRORS:
            if isinstance(error, litellm_types):
                return provider_type(
                    f"Decision request to {self.litellm_model} failed: {error!r}"
                )
        return None
