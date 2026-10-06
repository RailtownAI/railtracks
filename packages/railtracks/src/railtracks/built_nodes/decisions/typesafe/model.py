from __future__ import annotations

import os
import re
from typing import Any, TypeVar

import httpx

from railtracks.classifiers._exceptions import (
    ClassifierAuthenticationError,
    ClassifierConnectionError,
    ClassifierError,
    ClassifierRateLimitError,
    ClassifierRequestError,
    ClassifierResponseError,
    ClassifierServerError,
    ClassifierTimeoutError,
)
from railtracks.classifiers.model import DecisionModel, DecisionReply
from railtracks.classifiers.models.system_one._wire import (
    build_request,
    parse_response,
    questions_to_wire,
)
from railtracks.classifiers.models.system_one.schema import TypeSafeSchema
from railtracks.classifiers.response import DecisionResponse
from railtracks.classifiers.schema import DecisionState
from railtracks.llm.retries import RetryApproach

DEFAULT_PROVIDER = "typesafe"
DEFAULT_API_BASE = "https://api.typesafe.ai"
SYSTEM_ONE_PATH = "/v1/systemone"
_MAX_ERROR_BODY = 500

_TSchema = TypeVar("_TSchema", bound=TypeSafeSchema)


class TypeSafeAI(DecisionModel[TypeSafeSchema]):
    """A System One model served over TypeSafe's ``/v1/systemone`` format.

    Reaches TypeSafe itself and compatible hosts (OpenRouter's mirror, self-hosted
    Laya, Bespoke Nimble or Kev servers, a LiteLLM proxy's TypeSafe route) through
    ``api_base``; ``provider`` names the host for pricing and its API key variable.
    """

    schema_base = TypeSafeSchema

    def __init__(
        self,
        model_name: str,
        *,
        provider: str = DEFAULT_PROVIDER,
        api_key: str | None = None,
        api_base: str = DEFAULT_API_BASE,
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
        retry_approach: RetryApproach | None = None,
    ) -> None:
        """Create a TypeSafe System One client. Nothing is sent until a call.

        Args:
            model_name: The model to ask, e.g. ``"jev-latest"``.
            provider: Who serves the model, e.g. ``"typesafe"``, ``"laya"``,
                ``"bespoke"`` or ``"openrouter"``. It prefixes the pricing lookup
                (``litellm.model_cost["laya/english"]``) and names the API key
                variable (``LAYA_API_KEY``).
            api_key: The API key. Defaults to the ``<PROVIDER>_API_KEY`` environment
                variable, read at call time. Required for TypeSafe's hosted API;
                elsewhere a missing key sends the request without authentication,
                for self-hosted servers that don't use it.
            api_base: The server's base URL, without ``/v1/systemone``.
            timeout: Seconds to wait for each HTTP request.
            http_client: An ``httpx.AsyncClient`` to send requests through, e.g. for a
                proxy or a mock transport in tests. The caller owns and closes it.
                Without one, each call opens and closes its own client.
            retry_approach: Retry strategy for rate limits, timeouts and 5xx errors.
                None (the default) makes one attempt, as for LLM providers.
        """
        super().__init__(model_name, api_base=api_base, retry_approach=retry_approach)
        self.provider = provider
        self.api_key_env = re.sub(r"[^A-Z0-9]+", "_", provider.upper()) + "_API_KEY"
        self._api_key = api_key
        self._timeout = timeout
        self._http_client = http_client

    async def aask(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionResponse[_TSchema]:
        """Answer every question in ``schema`` about ``state`` in one request.

        Args:
            state: What to judge: text, or a JSON object or array.
            schema: The ``TypeSafeSchema`` subclass declaring the questions.

        Returns:
            The answers as a ``schema`` instance, with model, token, latency and cost
            metadata.

        Raises:
            ClassifierError: If the call fails; the subclass says why.
        """
        return await self._ask(state, schema)

    def _pricing_keys(self) -> list[str]:
        keys = [
            f"{self.provider}/{self.model_name}",
            self.model_name,
            f"openrouter/{self.model_name}",
        ]
        return list(dict.fromkeys(keys))

    def describe_questions(self, schema: type[_TSchema]) -> dict[str, Any]:
        return questions_to_wire(schema)

    def _resolve_api_key(self) -> str | None:
        api_key = self._api_key or os.environ.get(self.api_key_env)
        if not api_key and self.api_base.rstrip("/") == DEFAULT_API_BASE:
            raise ClassifierAuthenticationError(
                "No TypeSafe API key was provided.",
                notes=[self._key_note()],
            )
        return api_key or None

    def _key_note(self) -> str:
        return f"Pass api_key= or set the {self.api_key_env} environment variable."

    async def _send(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
        api_key = self._resolve_api_key()
        url = self.api_base.rstrip("/") + SYSTEM_ONE_PATH
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
            raise ClassifierTimeoutError(f"No answer from {url} in time: {e!r}") from e
        except (httpx.InvalidURL, httpx.UnsupportedProtocol) as e:
            # a config mistake, not a transient failure: never retried
            raise ClassifierRequestError(
                f"Could not send to {url}: {e!r}",
                notes=["Check api_base: it must be an http(s) URL."],
            ) from e
        except httpx.TransportError as e:
            raise ClassifierConnectionError(f"Could not reach {url}: {e!r}") from e

        _raise_for_status(response, key_note=self._key_note())
        try:
            payload = response.json()
        except ValueError as e:
            raise ClassifierResponseError(
                f"Decision response from {url} is not JSON: {e!r}"
            ) from e
        return parse_response(payload, schema)


def _raise_for_status(response: httpx.Response, *, key_note: str) -> None:
    status = response.status_code
    if status < 400:
        return
    body = response.text[:_MAX_ERROR_BODY]
    reason = f"HTTP {status} from {response.request.url}: {body}"
    error: ClassifierError
    if status in (401, 403):
        error = ClassifierAuthenticationError(reason, notes=[key_note])
    elif status == 429:
        error = ClassifierRateLimitError(reason)
    elif status >= 500:
        error = ClassifierServerError(reason)
    else:
        error = ClassifierRequestError(reason, body=body)
    raise error
