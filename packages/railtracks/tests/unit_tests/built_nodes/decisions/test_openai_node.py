"""decision_node with OpenAI's Decisions API: Flow, agent str() and refusals."""

import copy

import httpx
import pytest
import railtracks as rt
from railtracks.decisions import DecisionProviderRefusalError, OpenAIDecisions
from railtracks.exceptions import DecisionModelError, DecisionRefusalError

from ...decisions.test_openai import LIVE_RESPONSE, Triage


def _node(body: dict):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )
    model = OpenAIDecisions("gpt-6-luna", api_key="sk-test", http_client=client)
    return rt.decision_node("Triage Ticket", model=model, schema=Triage)


def test_flow_returns_the_typed_response():
    result = rt.Flow(name="OpenAI Triage", entry_point=_node(LIVE_RESPONSE)).invoke(
        "My checkout is down."
    )
    assert result.structured.department.choice == "technical"
    assert (
        str(result)
        == "is_urgent: yes 0.99 | department: technical 1.00 | frustration: 1.1/2"
    )


def test_refusal_becomes_a_decision_refusal_error():
    body = copy.deepcopy(LIVE_RESPONSE)
    body["answers"][1] = {"type": "refusal", "name": "department"}

    with pytest.raises(DecisionRefusalError) as info:
        rt.Flow(name="OpenAI Triage", entry_point=_node(body)).invoke("x")

    assert isinstance(info.value, DecisionModelError)
    assert info.value.refused == ["department"]
    assert isinstance(info.value.__cause__, DecisionProviderRefusalError)
