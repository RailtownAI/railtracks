"""decision_node with OpenAI's Decisions API: Flow, agent str() and refusals."""

import copy

import litellm
import pytest
import railtracks as rt
from railtracks.decisions import DecisionProviderRefusalError, OpenAIDecisions
from railtracks.exceptions import DecisionModelError, DecisionRefusalError

from .conftest import TRIAGE_BODY, FakeDecisions, Triage, respond


def _node(monkeypatch, body: dict):
    monkeypatch.setattr(litellm, "adecisions", FakeDecisions(respond(body)))
    model = OpenAIDecisions("gpt-6-luna", api_key="sk-test")
    return rt.decision_node("Triage Ticket", model=model, schema=Triage)


def test_flow_returns_the_typed_response(monkeypatch):
    body = copy.deepcopy(TRIAGE_BODY)
    body["model"] = "gpt-6-luna"
    result = rt.Flow(name="OpenAI Triage", entry_point=_node(monkeypatch, body)).invoke(
        "My checkout is down."
    )
    assert result.structured.department.choice == "technical"
    assert result.model_name == "gpt-6-luna"
    assert result.provider == "openai"
    assert (
        str(result)
        == "is_urgent: yes 0.93 | department: technical 0.88 | frustration: 1.7/2"
    )


def test_refusal_becomes_a_decision_refusal_error(monkeypatch):
    body = copy.deepcopy(TRIAGE_BODY)
    body["answers"][1] = {"type": "refusal", "name": "department"}

    with pytest.raises(DecisionRefusalError) as info:
        rt.Flow(name="OpenAI Triage", entry_point=_node(monkeypatch, body)).invoke("x")

    assert isinstance(info.value, DecisionModelError)
    assert info.value.refused == ["department"]
    assert isinstance(info.value.__cause__, DecisionProviderRefusalError)
