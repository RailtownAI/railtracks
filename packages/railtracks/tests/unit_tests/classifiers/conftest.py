"""Shared fixtures for decision tests: a Triage schema and documented wire examples.

The example bodies are the TypeSafe docs' examples (https://docs.typesafe.ai/primitives/)
merged into one response for the Triage schema.
"""

import json
from typing import Callable

import httpx
import pytest
from railtracks.classifiers import TypeSafeAI, TypeSafeSchema


class Triage(TypeSafeSchema):
    is_urgent = TypeSafeSchema.Noul(instructions="The message conveys urgency")
    department = TypeSafeSchema.Choice(
        instructions="Which team should handle this",
        criteria={
            "billing": "Charges, refunds, invoices, or plan changes",
            "technical": "Bugs, outages, errors, or integration problems",
            "sales": "Pricing questions, upgrades, or new purchases",
        },
    )
    frustration = TypeSafeSchema.Score(
        instructions="How frustrated the customer is",
        criteria=["Calm", "Frustrated but civil", "Very angry"],
    )


TRIAGE_RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "is_urgent": {"type": "noul", "noul": 0.93},
        "department": {
            "type": "choice",
            "choice": "technical",
            "confidence": 0.81,
            "probabilities": {"billing": 0.02, "technical": 0.88, "sales": 0.1},
        },
        "frustration": {
            "type": "score",
            "score": 1.7,
            "confidence": 0.6,
            "legend": {"0": "Calm", "1": "Frustrated but civil", "2": "Very angry"},
            "probabilities": {"0": 0.05, "1": 0.2, "2": 0.75},
        },
    },
    "usage": {"input_tokens": 296, "output_tokens": 20},
}

Handler = Callable[[httpx.Request], httpx.Response]


class Recorder:
    """An ``httpx.MockTransport`` handler that records requests and replays responses."""

    def __init__(self, *responses: httpx.Response | Exception):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = (
            self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        )
        if isinstance(response, Exception):
            raise response
        return response

    def body(self, index: int = -1) -> dict:
        return json.loads(self.requests[index].content)


def ok(body: dict | None = None) -> httpx.Response:
    return httpx.Response(200, json=TRIAGE_RESPONSE if body is None else body)


@pytest.fixture
def make_model() -> Callable[..., tuple[TypeSafeAI, Recorder]]:
    """Build a ``TypeSafeAI`` whose HTTP goes to a ``Recorder`` instead of the network."""

    def _make(
        *responses: httpx.Response | Exception, **kwargs
    ) -> tuple[TypeSafeAI, Recorder]:
        recorder = Recorder(*(responses or (ok(),)))
        client = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
        kwargs.setdefault("api_key", "test-key")
        model_name = kwargs.pop("model_name", "jev-latest")
        return TypeSafeAI(model_name, http_client=client, **kwargs), recorder

    return _make
