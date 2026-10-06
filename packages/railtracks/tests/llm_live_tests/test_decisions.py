"""Live System One decision calls through OpenRouter (Jev 1.13).

Each call costs about $0.00002. Skipped without OPENROUTER_API_KEY.
"""

import os

import httpx
import pytest
import railtracks as rt
import railtracks.context.central as central
from railtracks.observability import Event, configure, configure_writers

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"), reason="OPENROUTER_API_KEY not set"
)

MODEL = "typesafe/jev-1.13"
TypeSafeSchema = rt.decisions.TypeSafeSchema


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


BILLING = "I was charged twice for my March invoice. Please refund the duplicate."
OUTAGE = (
    "Your API has returned 502s for an hour and our checkout is down. FIX THIS NOW."
)
SALES = "We're a team of 40. Is there volume pricing on the Business plan?"


@pytest.fixture(autouse=True)
def _clean_observability():
    central.delete_globals()
    configure.reset_for_tests()
    yield
    central.delete_globals()
    configure.reset_for_tests()


class _Collecting:
    def __init__(self):
        self.events: list[Event] = []

    async def start(self):
        pass

    async def write(self, event: Event):
        self.events.append(event)

    async def shutdown(self):
        pass


async def test_aask_parses_every_answer_type_and_the_metadata():
    resp = await rt.decisions.OpenRouterAI(MODEL).aask(OUTAGE, Triage)

    assert resp.structured.department.choice == "technical"
    assert resp.structured.is_urgent.noul > 0.5
    assert set(resp.structured.frustration.legend) == {0, 1, 2}
    assert 0.0 <= resp.structured.frustration.score <= 2.0
    assert resp.model_name.startswith(MODEL)
    assert resp.requested_model_name == MODEL
    assert resp.provider  # OpenRouter reports who served it
    assert resp.input_tokens and resp.input_tokens > 0
    assert resp.cost and resp.cost > 0  # OpenRouter's billed usage.cost
    assert resp.latency > 0


async def test_json_state():
    state = {"subject": "Duplicate charge", "body": BILLING}
    resp = await rt.decisions.OpenRouterAI(MODEL).aask(state, Triage)
    assert resp.structured.department.choice == "billing"


def test_decision_node_in_a_flow_records_paired_events():
    writer = _Collecting()
    configure_writers([writer])
    node = rt.decision_node(
        "Triage Ticket", model=rt.decisions.OpenRouterAI(MODEL), schema=Triage
    )

    result = rt.Flow(name="Live Triage", entry_point=node).invoke(OUTAGE)

    assert result.structured.department.choice == "technical"
    invocation, response = [
        e for e in writer.events if e.event_type.startswith("decision.")
    ]
    assert invocation.event_type == "decision.invocation"
    assert response.event_type == "decision.response"
    assert invocation.payload["decision_id"] == response.payload["decision_id"]
    assert response.payload["total_cost"] == result.cost


async def test_call_batch_preserves_order():
    node = rt.decision_node(model=rt.decisions.OpenRouterAI(MODEL), schema=Triage)

    with rt.Session(flow_name="Live Batch"):
        results = await rt.call_batch(node, [BILLING, OUTAGE, SALES])

    assert [r.structured.department.choice for r in results] == [
        "billing",
        "technical",
        "sales",
    ]


async def test_rejected_key_is_an_auth_error_and_not_retried():
    requests: list[httpx.Request] = []

    async def count(request: httpx.Request) -> None:
        requests.append(request)

    async with httpx.AsyncClient(event_hooks={"request": [count]}) as client:
        model = rt.decisions.OpenRouterAI(
            MODEL,
            api_key="sk-or-v1-not-a-real-key",
            http_client=client,
            retry_approach=rt.llm.retries.FixedRetry(max_tries=3, delay=0.0),
        )
        with pytest.raises(rt.decisions.DecisionProviderAuthenticationError):
            await model.aask(OUTAGE, Triage)

    assert len(requests) == 1
