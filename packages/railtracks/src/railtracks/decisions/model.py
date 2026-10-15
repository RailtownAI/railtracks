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
from typing import Any, ClassVar

import litellm

from railtracks.llm.retries import RetryApproach, RetryError

from ._exceptions import (
    DecisionProviderAuthenticationError,
    DecisionProviderError,
    DecisionProviderRateLimitError,
    DecisionProviderTimeoutError,
)
from .pricing import decision_cost
from .response import DecisionResponse
from .schema import DecisionSchema
from .state import DecisionInput
from .transport._client_cleanup import close_client_on_loop_shutdown
from .transport._wire import parse_response, questions_to_wire, to_input

# litellm prints a "Give Feedback / Get Help" banner on every mapped error without it
litellm.suppress_debug_info = True

# Checked in order; any other litellm exception is a plain DecisionProviderError.
# litellm.Timeout comes first: it is an openai.APIConnectionError (though not a
# litellm.APIConnectionError), and timeouts are not provider-tagged.
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

    Attributes:
        provider_prefix: litellm's provider name, prefixed to the model name
            (``"typesafe/jev-latest"``).
        provider_name: Who serves the model: the response's ``provider``.
        bills_output_tokens: Whether catalog pricing should charge output tokens; False
            when the API bills input only (OpenAI's Decisions API) but the catalog lists
            chat prices.
        pricing_prefixes: Prefixes tried, in order, before the bare model name when
            looking the model up in ``litellm.model_cost``.
    """

    provider_prefix: ClassVar[str]
    provider_name: ClassVar[str]
    bills_output_tokens: ClassVar[bool] = True
    pricing_prefixes: ClassVar[tuple[str, ...]] = ()

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
        """
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
        hidden = getattr(response, "_hidden_params", None) or {}
        cost = _optional_cost(hidden.get("response_cost"))
        if not self.bills_output_tokens and parsed.output_tokens:
            # litellm prices output at the catalog's chat rate; the API bills none
            cost = None
        if cost is None:
            cost = decision_cost(
                self._pricing_keys(),
                parsed.input_tokens,
                parsed.output_tokens if self.bills_output_tokens else None,
            )
        return dataclasses.replace(parsed, cost=cost)

    async def _adecisions(self, state: DecisionInput, schema: DecisionSchema) -> Any:
        """One ``litellm.adecisions`` call, retried per ``retry_approach``."""

        async def adecisions() -> Any:
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

    def _pricing_keys(self) -> list[str]:
        """The ``litellm.model_cost`` keys to try for this model, in order."""
        keys = [f"{prefix}/{self.model_name}" for prefix in self.pricing_prefixes]
        return list(dict.fromkeys([*keys, self.model_name]))
