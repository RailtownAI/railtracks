"""Shared fixtures for decision tests: a Triage schema and a mocked ``litellm.adecisions``.

The responses are ``OpenAIDecisionResponse`` objects shaped as litellm 1.104.2 returns
them for an OpenAI-shape request (answers in question order, carrying their ``name``;
cost in ``_hidden_params["response_cost"]``).
"""

from typing import Any, Callable

import litellm
import pytest
from litellm.types.decisions import OpenAIDecisionResponse
from railtracks.decisions import (
    Choice,
    DecisionModel,
    DecisionSchema,
    Predicate,
    Score,
    TypeSafeAI,
)

_PROVIDER_ENV = (
    "TYPESAFE_API_KEY",
    "TYPESAFE_API_BASE",
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_BASE",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
)


IS_URGENT = Predicate(name="is_urgent", instructions="The message conveys urgency")
DEPARTMENT = Choice(
    name="department",
    instructions="Which team should handle this",
    choices={
        "billing": "Charges, refunds, invoices, or plan changes",
        "technical": "Bugs, outages, errors, or integration problems",
        "sales": "Pricing questions, upgrades, or new purchases",
    },
)
FRUSTRATION = Score(
    name="frustration",
    instructions="How frustrated the customer is",
    levels=["Calm", "Frustrated but civil", "Very angry"],
)
Triage = DecisionSchema(predicate=[IS_URGENT], choice=[DEPARTMENT], score=[FRUSTRATION])


TRIAGE_COST = 296 * 4.2e-08

TRIAGE_BODY: dict[str, Any] = {
    "model": "jev-1.13.0",
    "answers": [
        {"type": "predicate", "name": "is_urgent", "probability": 0.93},
        {
            "type": "choice",
            "name": "department",
            "choice": "technical",
            "probabilities": [
                {"value": "billing", "probability": 0.02},
                {"value": "technical", "probability": 0.88},
                {"value": "sales", "probability": 0.1},
            ],
            "confidence": 0.81,
        },
        {
            "type": "score",
            "name": "frustration",
            "score": 1.7,
            "probabilities": [
                {"value": 0, "label": "Calm", "probability": 0.05},
                {"value": 1, "label": "Frustrated but civil", "probability": 0.2},
                {"value": 2, "label": "Very angry", "probability": 0.75},
            ],
            "confidence": 0.6,
        },
    ],
    "usage": {
        "input_tokens": 296,
        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        "output_tokens": 20,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": 316,
    },
}


def respond(
    body: dict[str, Any] | None = None, *, cost: float | None = TRIAGE_COST
) -> OpenAIDecisionResponse:
    """An ``OpenAIDecisionResponse`` for ``body`` (default: the Triage answers), with
    ``response_cost`` in its hidden params unless ``cost`` is None."""
    response = OpenAIDecisionResponse.model_validate(
        TRIAGE_BODY if body is None else body
    )
    if cost is not None:
        response._hidden_params["response_cost"] = cost
    return response


class FakeDecisions:
    """Stands in for ``litellm.adecisions``: records each call's kwargs and replays the
    outcomes in order (the last one repeats); an exception outcome is raised."""

    def __init__(self, *outcomes: OpenAIDecisionResponse | Exception):
        self.outcomes = list(outcomes) or [respond()]
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> OpenAIDecisionResponse:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    @property
    def last(self) -> dict[str, Any]:
        return self.calls[-1]


@pytest.fixture(autouse=True)
def _no_provider_env(monkeypatch):
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def fake_decisions(monkeypatch) -> Callable[..., FakeDecisions]:
    """Patch ``litellm.adecisions`` with a ``FakeDecisions`` replaying ``outcomes``."""

    def _install(*outcomes: OpenAIDecisionResponse | Exception) -> FakeDecisions:
        fake = FakeDecisions(*outcomes)
        monkeypatch.setattr(litellm, "adecisions", fake)
        return fake

    return _install


@pytest.fixture
def make_model(fake_decisions) -> Callable[..., tuple[DecisionModel, FakeDecisions]]:
    """Build a provider client (``TypeSafeAI`` unless ``cls=`` says otherwise) whose
    ``litellm.adecisions`` calls go to a ``FakeDecisions``."""

    def _make(
        *outcomes: OpenAIDecisionResponse | Exception,
        cls: type[DecisionModel] = TypeSafeAI,
        model_name: str = "jev-latest",
        **kwargs: Any,
    ) -> tuple[DecisionModel, FakeDecisions]:
        fake = fake_decisions(*outcomes)
        kwargs.setdefault("api_key", "test-key")
        return cls(model_name, **kwargs), fake

    return _make
