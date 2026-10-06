"""The base client for every host that speaks the ``/v1/systemone`` format.

The counterpart of ``OpenAICompatibleProvider``: one request/response format, many
hosts. A host subclass only sets class attributes (its URL, key variable, pricing
prefixes and limits); request building, auth, sending, status mapping and parsing
live here.
"""

from __future__ import annotations

import json
import os
from typing import Any, TypeVar

import httpx

from railtracks.llm.retries import RetryApproach

from ..._exceptions import (
    DecisionProviderAuthenticationError,
    DecisionProviderConnectionError,
    DecisionProviderError,
    DecisionProviderRateLimitError,
    DecisionProviderRequestError,
    DecisionProviderResponseError,
    DecisionProviderServerError,
    DecisionProviderTimeoutError,
)
from ...model import DecisionModel, DecisionReply
from ...response import DecisionResponse
from ...schema import DecisionSchema, DecisionState
from ._wire import build_request, parse_response, questions_to_wire, typesafe_questions
from .schema import ChoiceQuestion, TypeSafeSchema

SYSTEM_ONE_PATH = "/v1/systemone"
_MAX_ERROR_BODY = 500

_TTypeSafe = TypeVar("_TTypeSafe", bound=TypeSafeSchema)
# the base class's internal hooks take any DecisionSchema; _wire checks the format
_TSchema = TypeVar("_TSchema", bound=DecisionSchema)


class TypeSafeCompatibleAI(DecisionModel[TypeSafeSchema]):
    """Any server that speaks TypeSafe's ``/v1/systemone`` format.

    Use it directly for a server with no class of its own, such as self-hosted Kev or
    CLM: ``api_base`` is required, ``api_key`` is optional, no environment variable is
    read, and pricing looks up the bare model name::

        kev = TypeSafeCompatibleAI(
            model_name="jaredpalmer/kev-4b", api_base="http://localhost:8008"
        )

    The named hosts (``TypeSafeAI``, ``OpenRouterAI``, ``LayaAI``, ``LiteLLMProxyAI``)
    subclass it and only set the class attributes below.

    Attributes:
        provider_name: Who serves the model: the response's ``provider`` when the
            host reports none.
        default_api_base: The base URL when neither ``api_base=`` nor
            ``api_base_env`` gives one. None means the user must supply it.
        api_base_env: Environment variable read for the base URL at call time.
        api_key_env: Environment variable read for the API key at call time.
        requires_api_key: Whether a missing key fails before any request. When False,
            a missing key sends the request without authentication.
        path: The endpoint, appended to the base URL.
        pricing_prefixes: Prefixes tried, in order, before the bare model name when
            looking the model up in ``litellm.model_cost``.
        max_choice_labels: The host's cap on a Choice question's options, if stricter
            than the format's 255.
        max_questions: The host's cap on questions per request.
        max_state_chars: The host's cap on the state's length (JSON states are
            measured as serialized JSON).
    """

    schema_base = TypeSafeSchema
    provider_name: str = "typesafe_compatible"
    default_api_base: str | None = None
    api_base_env: str | None = None
    api_key_env: str | None = None
    requires_api_key: bool = False
    path: str = SYSTEM_ONE_PATH
    pricing_prefixes: tuple[str, ...] = ()
    max_choice_labels: int | None = None
    max_questions: int | None = None
    max_state_chars: int | None = None

    def __init__(
        self,
        model_name: str,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
        retry_approach: RetryApproach | None = None,
    ) -> None:
        """Create a client. Nothing is sent, and no environment is read, until a call.

        Args:
            model_name: The model to ask, e.g. ``"jev-latest"``.
            api_key: The API key. Defaults to the ``api_key_env`` variable, read at
                call time.
            api_base: The server's base URL, without the endpoint path. Defaults to the
                ``api_base_env`` variable, then the host's ``default_api_base``.
            timeout: Seconds to wait for each HTTP request.
            http_client: An ``httpx.AsyncClient`` to send requests through, e.g. for a
                proxy or a mock transport in tests. The caller owns and closes it.
                Without one, each call opens and closes its own client.
            retry_approach: Retry strategy for rate limits, timeouts, connection
                failures and 5xx errors. None (the default) makes one attempt, as for
                LLM providers.
        """
        super().__init__(model_name, retry_approach=retry_approach)
        self._api_key = api_key
        self._api_base = api_base
        self._timeout = timeout
        self._http_client = http_client

    @property
    def api_base(self) -> str | None:
        """The base URL the next call goes to, or None if none is configured."""
        from_env = os.environ.get(self.api_base_env) if self.api_base_env else None
        return self._api_base or from_env or self.default_api_base

    async def aask(
        self, state: DecisionState, schema: type[_TTypeSafe]
    ) -> DecisionResponse[_TTypeSafe]:
        """Answer every question in ``schema`` about ``state`` in one request.

        Args:
            state: What to judge: text, or a JSON object or array.
            schema: The ``TypeSafeSchema`` subclass declaring the questions.

        Returns:
            The answers as a ``schema`` instance, with model, token, latency and cost
            metadata.

        Raises:
            DecisionProviderError: If the call fails; the subclass says why.
        """
        return await self._ask(state, schema)

    def describe_questions(self, schema: type[_TSchema]) -> dict[str, Any]:
        return questions_to_wire(schema)

    def _pricing_keys(self) -> list[str]:
        keys = [f"{prefix}/{self.model_name}" for prefix in self.pricing_prefixes]
        return list(dict.fromkeys([*keys, self.model_name]))

    def _check_request(self, state: DecisionState, schema: type[_TSchema]) -> None:
        host = type(self).__name__
        questions = typesafe_questions(schema)
        if self.max_questions is not None and len(questions) > self.max_questions:
            raise DecisionProviderRequestError(
                f"{host} accepts at most {self.max_questions} questions per request; "
                f"{schema.__name__} has {len(questions)}."
            )
        if self.max_choice_labels is not None:
            for name, question in questions.items():
                if (
                    isinstance(question, ChoiceQuestion)
                    and len(question.criteria) > self.max_choice_labels
                ):
                    raise DecisionProviderRequestError(
                        f"{host} accepts at most {self.max_choice_labels} options per "
                        f"Choice; {schema.__name__}.{name} has {len(question.criteria)}."
                    )
        if self.max_state_chars is not None:
            text = state if isinstance(state, str) else json.dumps(state)
            if len(text) > self.max_state_chars:
                raise DecisionProviderRequestError(
                    f"{host} accepts a state of at most {self.max_state_chars} "
                    f"characters; this one has {len(text)}."
                )

    def _key_notes(self) -> list[str]:
        """Debugging notes for a missing or rejected key."""
        if self.api_key_env is None:
            return ["Pass api_key=."]
        return [f"Pass api_key= or set the {self.api_key_env} environment variable."]

    def _resolve_api_key(self) -> str | None:
        from_env = os.environ.get(self.api_key_env) if self.api_key_env else None
        api_key = self._api_key or from_env
        if not api_key and self.requires_api_key:
            raise DecisionProviderAuthenticationError(
                f"No API key was provided for {type(self).__name__}.",
                notes=self._key_notes(),
            )
        return api_key or None

    def _resolve_url(self) -> str:
        api_base = self.api_base
        if not api_base:
            where = f"set {self.api_base_env} or " if self.api_base_env else ""
            raise DecisionProviderRequestError(
                f"No base URL is configured for {type(self).__name__}.",
                notes=[f"Pass api_base=, or {where}point it at your server."],
            )
        return api_base.rstrip("/") + self.path

    async def _send(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
        url = self._resolve_url()
        api_key = self._resolve_api_key()
        body = build_request(self.model_name, state, schema)
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    url, json=body, headers=headers, timeout=self._timeout
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, json=body, headers=headers)
        except httpx.TimeoutException as e:
            raise DecisionProviderTimeoutError(
                f"No answer from {url} in time: {e!r}"
            ) from e
        except (httpx.InvalidURL, httpx.UnsupportedProtocol) as e:
            # a config mistake, not a transient failure: never retried
            raise DecisionProviderRequestError(
                f"Could not send to {url}: {e!r}",
                notes=["Check api_base: it must be an http(s) URL."],
            ) from e
        except httpx.TransportError as e:
            raise DecisionProviderConnectionError(
                f"Could not reach {url}: {e!r}"
            ) from e

        self._raise_for_status(response)
        try:
            payload = response.json()
        except ValueError as e:
            raise DecisionProviderResponseError(
                f"Decision response from {url} is not JSON: {e!r}"
            ) from e
        return parse_response(payload, schema)

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if status < 400:
            return
        body = response.text[:_MAX_ERROR_BODY]
        reason = f"HTTP {status} from {response.request.url}: {body}"
        error: DecisionProviderError
        if status in (401, 403):
            error = DecisionProviderAuthenticationError(reason, notes=self._key_notes())
        elif status == 429:
            error = DecisionProviderRateLimitError(reason)
        elif status >= 500:
            error = DecisionProviderServerError(reason)
        else:
            error = DecisionProviderRequestError(reason, body=body)
        raise error
