"""``OpenAIDecisions``: OpenAI's Decisions API (``POST /v1/decisions``)."""

from __future__ import annotations

from typing import Any, TypeVar

from ..._exceptions import DecisionProviderRequestError
from ...model import DecisionReply
from ...response import DecisionResponse
from ...schema import DecisionSchema, DecisionState
from .._http import HTTPDecisionModel
from ._wire import (
    build_request,
    is_user_messages,
    openai_questions,
    parse_response,
    questions_to_wire,
)
from .schema import OpenAISchema

MAX_IMAGE_PARTS = 128

_TOpenAI = TypeVar("_TOpenAI", bound=OpenAISchema)
# the base class's internal hooks take any DecisionSchema; _wire checks the format
_TSchema = TypeVar("_TSchema", bound=DecisionSchema)


class OpenAIDecisions(HTTPDecisionModel[OpenAISchema]):
    """OpenAI's Decisions API, e.g. ``gpt-6-luna`` (public beta since 2026-10-06).

    Reads ``OPENAI_API_KEY`` (required) and, optionally, ``OPENAI_BASE_URL``, as the
    official SDK does. The input can be text, other JSON (sent as JSON text), or a list
    of user messages with ``input_text`` and inline ``input_image`` parts, at most 128
    images per request. Guide: https://developers.openai.com/api/docs/guides/decisions.

    Pricing uses the catalog's input price only: the API bills input tokens alone,
    while ``litellm.model_cost`` lists ``gpt-6-luna`` at chat prices.
    """

    schema_base = OpenAISchema
    provider_name = "openai"
    default_api_base = "https://api.openai.com/v1"
    api_base_env = "OPENAI_BASE_URL"
    api_key_env = "OPENAI_API_KEY"
    requires_api_key = True
    path = "/decisions"
    bills_output_tokens = False

    async def aask(
        self, state: DecisionState, schema: type[_TOpenAI]
    ) -> DecisionResponse[_TOpenAI]:
        """Answer every question in ``schema`` about ``state`` in one request.

        Args:
            state: What to judge: text, a JSON object or array (sent as JSON text), or
                a list of user messages, which may include inline images.
            schema: The ``OpenAISchema`` subclass declaring the questions.

        Returns:
            The answers as a ``schema`` instance, with model, token, latency and cost
            metadata.

        Raises:
            DecisionProviderRefusalError: If the model declines any question.
            DecisionProviderError: If the call fails otherwise; the subclass says why.
        """
        return await self._ask(state, schema)

    def describe_questions(self, schema: type[_TSchema]) -> dict[str, Any]:
        return questions_to_wire(schema)

    def _build_body(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> dict[str, Any]:
        return build_request(self.model_name, state, schema)

    def _parse_reply(
        self, payload: object, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
        return parse_response(payload, schema)

    def _check_request(self, state: DecisionState, schema: type[_TSchema]) -> None:
        openai_questions(schema)
        if not isinstance(state, list) or not is_user_messages(state):
            return
        images = sum(
            1
            for message in state
            if isinstance(message.get("content"), list)
            for part in message["content"]
            if isinstance(part, dict) and part.get("type") == "input_image"
        )
        if images > MAX_IMAGE_PARTS:
            raise DecisionProviderRequestError(
                f"OpenAI's Decisions API accepts at most {MAX_IMAGE_PARTS} images per "
                f"request; this input has {images}."
            )
