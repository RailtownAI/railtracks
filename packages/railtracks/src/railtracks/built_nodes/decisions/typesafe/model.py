from __future__ import annotations

import os
from typing import Any, TypeVar

import httpx

from railtracks.exceptions import (
    DecisionAuthenticationError,
    DecisionModelError,
    DecisionRateLimitError,
    DecisionRequestError,
    DecisionResponseError,
    DecisionServerError,
    DecisionTimeoutError,
)
from railtracks.llm.retries import RetryApproach

from .._base import DecisionModel, DecisionReply, DecisionState
from ..response import DecisionResponse
from ._wire import build_request, parse_response, questions_to_wire
from .schema import TypeSafeSchema

API_KEY_ENV = "TYPESAFE_API_KEY"
DEFAULT_API_BASE = "https://api.typesafe.ai"
SYSTEM_ONE_PATH = "/v1/systemone"
_MAX_ERROR_BODY = 500

_TSchema = TypeVar("_TSchema", bound=TypeSafeSchema)


class TypeSafeAI(DecisionModel[TypeSafeSchema]):
    """A System One model served over TypeSafe's ``/v1/systemone`` format.

    Reaches TypeSafe itself and compatible hosts (OpenRouter's mirror, a self-hosted
    Kev server, a LiteLLM proxy's TypeSafe route) through ``api_base``.
    """

    schema_base = TypeSafeSchema

    def __init__(
        self,
        model_name: str,
        *,
        api_key: str | None = None,
        api_base: str = DEFAULT_API_BASE,
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
        retry_approach: RetryApproach | None = None,
    ) -> None:
        """Create a TypeSafe System One client. Nothing is sent until a call.

        Args:
            model_name: The model to ask, e.g. ``"jev-latest"``.
            api_key: The API key. Defaults to the ``TYPESAFE_API_KEY`` environment
                variable, read at call time.
            api_base: The server's base URL, without ``/v1/systemone``.
            timeout: Seconds to wait for each HTTP request.
            http_client: An ``httpx.AsyncClient`` to send requests through, e.g. for a
                proxy or a mock transport in tests. The caller owns and closes it.
                Without one, each call opens and closes its own client.
            retry_approach: Retry strategy for rate limits, timeouts and 5xx errors.
                None (the default) makes one attempt, as for LLM providers.
        """
        super().__init__(model_name, api_base=api_base, retry_approach=retry_approach)
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
            DecisionModelError: If the call fails; the subclass says why.
        """
        return await self._ask(state, schema)

    def _pricing_keys(self) -> list[str]:
        return [
            f"typesafe/{self.model_name}",
            self.model_name,
            f"openrouter/{self.model_name}",
        ]

    def _describe_questions(self, schema: type[_TSchema]) -> dict[str, Any]:
        return questions_to_wire(schema)

    def _resolve_api_key(self) -> str:
        api_key = self._api_key or os.environ.get(API_KEY_ENV)
        if not api_key:
            raise DecisionAuthenticationError(
                "No TypeSafe API key was provided.",
                notes=[f"Pass api_key= or set the {API_KEY_ENV} environment variable."],
            )
        return api_key

    async def _send(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
        api_key = self._resolve_api_key()
        url = self.api_base.rstrip("/") + SYSTEM_ONE_PATH
        body = build_request(self.model_name, state, schema)
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    url, json=body, headers=headers, timeout=self._timeout
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, json=body, headers=headers)
        except httpx.TransportError as e:
            raise DecisionTimeoutError(
                f"Could not get an answer from {url}: {e!r}"
            ) from e

        _raise_for_status(response)
        try:
            payload = response.json()
        except ValueError as e:
            raise DecisionResponseError(
                f"Decision response from {url} is not JSON: {e!r}"
            ) from e
        return parse_response(payload, schema)


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status < 400:
        return
    body = response.text[:_MAX_ERROR_BODY]
    reason = f"HTTP {status} from {response.request.url}: {body}"
    error: DecisionModelError
    if status in (401, 403):
        error = DecisionAuthenticationError(
            reason, notes=[f"Check the API key (api_key= or {API_KEY_ENV})."]
        )
    elif status == 429:
        error = DecisionRateLimitError(reason)
    elif status >= 500:
        error = DecisionServerError(reason)
    else:
        error = DecisionRequestError(reason, body=body)
    raise error
