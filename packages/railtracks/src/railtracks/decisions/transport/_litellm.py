"""``LiteLLMDecisionModel``: every decision provider, called through ``litellm.adecisions``.

The counterpart of ``llm/models/_litellm_wrapper.py``: litellm owns the provider's URL,
key lookup and wire translation; this base sends the OpenAI-shape request (``_wire``),
maps litellm's exceptions to ``DecisionProviderError`` and reads usage, model and cost.
A provider subclass only sets class attributes.
"""

from __future__ import annotations

import os
from typing import Any, ClassVar, TypeVar
from urllib.parse import urlsplit

import litellm

from railtracks.llm.retries import RetryApproach

from .._exceptions import (
    DecisionProviderAuthenticationError,
    DecisionProviderConnectionError,
    DecisionProviderError,
    DecisionProviderRateLimitError,
    DecisionProviderRequestError,
    DecisionProviderResponseError,
    DecisionProviderServerError,
    DecisionProviderTimeoutError,
)
from ..model import DecisionModel, DecisionReply
from ..schema import DecisionSchema, DecisionState
from ._wire import describe_questions, parse_response, questions_to_wire, to_input

_MAX_ERROR_BODY = 500

_TSchema = TypeVar("_TSchema", bound=DecisionSchema)

# litellm prints a "Give Feedback / Get Help" banner on every mapped error without it
litellm.suppress_debug_info = True

# Checked in order. litellm.Timeout comes first: it is an openai.APIConnectionError
# (though not a litellm.APIConnectionError), and timeouts are not provider-tagged.
_LITELLM_ERRORS: tuple[
    tuple[tuple[type[Exception], ...], type[DecisionProviderError]], ...
] = (
    ((litellm.Timeout,), DecisionProviderTimeoutError),
    ((litellm.RateLimitError,), DecisionProviderRateLimitError),
    (
        (litellm.AuthenticationError, litellm.PermissionDeniedError),
        DecisionProviderAuthenticationError,
    ),
    ((litellm.APIConnectionError,), DecisionProviderConnectionError),
    (
        (
            litellm.InternalServerError,
            litellm.ServiceUnavailableError,
            litellm.BadGatewayError,
        ),
        DecisionProviderServerError,
    ),
    ((litellm.APIResponseValidationError,), DecisionProviderResponseError),
    (
        (
            litellm.BadRequestError,
            litellm.NotFoundError,
            litellm.UnprocessableEntityError,
        ),
        DecisionProviderRequestError,
    ),
)


def _optional_cost(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


class LiteLLMDecisionModel(DecisionModel):
    """A decision model reached through ``litellm.adecisions``.

    Attributes:
        provider_prefix: litellm's provider name, prefixed to the model name
            (``"typesafe/jev-latest"``).
        provider_name: Who serves the model: the response's ``provider``.
        default_api_base: The base URL litellm uses when neither ``api_base=`` nor
            ``api_base_env`` gives one; shown in ``decision.invocation`` events.
        api_base_env: The environment variable litellm reads for the base URL.
        api_key_env: The environment variable litellm reads for the API key, named in
            the notes of a missing or rejected key.
        pricing_prefixes: Prefixes tried, in order, before the bare model name when
            looking the model up in ``litellm.model_cost``.
    """

    provider_prefix: ClassVar[str]
    default_api_base: ClassVar[str]
    api_base_env: ClassVar[str]
    api_key_env: ClassVar[str]
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
            api_key: The API key. Defaults to the ``api_key_env`` variable, which
                litellm reads at call time.
            api_base: The server's base URL. Defaults to the ``api_base_env`` variable,
                then the provider's ``default_api_base``.
            timeout: Seconds to wait for each request.
            retry_approach: Retry strategy for rate limits, timeouts, connection
                failures and 5xx errors. None (the default) makes one attempt, as for
                LLM providers.
        """
        super().__init__(model_name, retry_approach=retry_approach)
        self._api_key = api_key
        self._api_base = api_base
        self._timeout = timeout

    @property
    def api_base(self) -> str:
        """The base URL the next call goes to."""
        return (
            self._api_base or os.environ.get(self.api_base_env) or self.default_api_base
        )

    def _check_api_base(self) -> None:
        """Raise ``DecisionProviderRequestError`` unless ``api_base`` is an http(s) URL.

        litellm reports a malformed base as a connection error, which would be retried.
        """
        api_base = self.api_base
        parts = urlsplit(api_base)
        if parts.scheme in ("http", "https") and parts.netloc:
            return
        source = (
            "the api_base= argument"
            if self._api_base
            else f"the {self.api_base_env} environment variable"
        )
        raise DecisionProviderRequestError(
            f"Malformed api_base {api_base!r} for {self.litellm_model}.",
            notes=[f"Set {source} to an http:// or https:// URL."],
        )

    @property
    def litellm_model(self) -> str:
        """The model name litellm routes on: ``"<provider_prefix>/<model_name>"``."""
        return f"{self.provider_prefix}/{self.model_name}"

    def describe_questions(self, schema: type[_TSchema]) -> dict[str, Any]:
        return describe_questions(schema)

    def _pricing_keys(self) -> list[str]:
        keys = [f"{prefix}/{self.model_name}" for prefix in self.pricing_prefixes]
        return list(dict.fromkeys([*keys, self.model_name]))

    async def _send(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
        self._check_api_base()
        try:
            response = await litellm.adecisions(
                model=self.litellm_model,
                input=to_input(state),
                questions=questions_to_wire(schema),
                api_key=self._api_key,
                api_base=self._api_base,
                timeout=self._timeout,
            )
        except Exception as e:
            error = self._provider_error(e)
            if error is None:
                raise
            raise error from e

        reply = parse_response(response, schema)
        hidden = getattr(response, "_hidden_params", None) or {}
        cost = _optional_cost(hidden.get("response_cost"))
        if not self.bills_output_tokens and reply.output_tokens:
            # litellm prices output at the catalog's chat rate; the API bills none
            cost = None
        return DecisionReply(
            structured=reply.structured,
            reported_model_name=reply.reported_model_name,
            provider=reply.provider,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            reported_cost=cost,
            raw=reply.raw,
        )

    def _provider_error(self, error: Exception) -> DecisionProviderError | None:
        """The ``DecisionProviderError`` for a litellm exception; None for any other."""
        target: type[DecisionProviderError] | None = None
        for litellm_types, provider_type in _LITELLM_ERRORS:
            if isinstance(error, litellm_types):
                target = provider_type
                break
        if target is None and isinstance(error, litellm.APIError):
            target = (
                DecisionProviderServerError
                if error.status_code >= 500
                else DecisionProviderRequestError
            )
        if target is None:
            return None

        reason = f"Decision request to {self.litellm_model} failed: {error!r}"
        if target is DecisionProviderRequestError:
            message = getattr(error, "message", None) or repr(error)
            return DecisionProviderRequestError(
                reason, body=str(message)[:_MAX_ERROR_BODY]
            )
        if target is DecisionProviderAuthenticationError:
            return DecisionProviderAuthenticationError(reason, notes=self._key_notes())
        return target(reason)

    def _key_notes(self) -> list[str]:
        """Debugging notes for a missing key, or for a key the provider rejected."""
        if self._api_key:
            source = "the api_key= argument"
        elif os.environ.get(self.api_key_env):
            source = f"the {self.api_key_env} environment variable"
        else:
            return [
                f"Pass api_key= or set the {self.api_key_env} environment variable."
            ]
        return [
            f"{self.provider_name} rejected the key from {source}; check that it is "
            f"a valid {self.provider_name} key."
        ]
