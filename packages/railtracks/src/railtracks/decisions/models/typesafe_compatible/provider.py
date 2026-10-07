"""The base client for every host that speaks the ``/v1/systemone`` format.

The counterpart of ``OpenAICompatibleProvider``: one request/response format, many
hosts. A host subclass only sets class attributes (its URL, key variable, pricing
prefixes and limits); the format lives here and the HTTP plumbing in ``.._http``.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

from ..._exceptions import DecisionProviderRequestError
from ...model import DecisionReply
from ...response import DecisionResponse
from ...schema import DecisionSchema, DecisionState
from .._http import HTTPDecisionModel
from ._wire import build_request, parse_response, questions_to_wire, typesafe_questions
from .schema import ChoiceQuestion, TypeSafeSchema

SYSTEM_ONE_PATH = "/v1/systemone"

_TTypeSafe = TypeVar("_TTypeSafe", bound=TypeSafeSchema)
# the base class's internal hooks take any DecisionSchema; _wire checks the format
_TSchema = TypeVar("_TSchema", bound=DecisionSchema)


class TypeSafeCompatibleAI(HTTPDecisionModel[TypeSafeSchema]):
    """Any server that speaks TypeSafe's ``/v1/systemone`` format.

    Use it directly for a server with no class of its own, such as self-hosted Kev or
    CLM: ``api_base`` is required, ``api_key`` is optional, no environment variable is
    read, and pricing looks up the bare model name::

        kev = TypeSafeCompatibleAI(
            model_name="jaredpalmer/kev-4b", api_base="http://localhost:8008"
        )

    The named hosts (``TypeSafeAI``, ``OpenRouterAI``, ``UpstageAI``, ``LayaAI``,
    ``LiteLLMProxyAI``) subclass it and only set class attributes: those of
    ``HTTPDecisionModel`` (URL, key variable, pricing prefixes) and the limits below.

    Attributes:
        max_choice_labels: The host's cap on a Choice question's options, if stricter
            than the format's 255.
        max_questions: The host's cap on questions per request.
        max_state_chars: The host's cap on the state's length (JSON states are
            measured as serialized JSON).
    """

    schema_base = TypeSafeSchema
    provider_name: str = "typesafe_compatible"
    path: str = SYSTEM_ONE_PATH
    max_choice_labels: int | None = None
    max_questions: int | None = None
    max_state_chars: int | None = None

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

    def _build_body(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> dict[str, Any]:
        return build_request(self.model_name, state, schema)

    def _parse_reply(
        self, payload: object, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
        return parse_response(payload, schema)

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
