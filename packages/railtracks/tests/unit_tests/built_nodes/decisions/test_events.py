"""decision.* events: emitted around aask inside a run, never outside one."""

import base64
import logging

import litellm
import pytest
import railtracks as rt
import railtracks.context.central as central
from railtracks.observability import Event, configure, configure_writers

from ...decisions.test_state import PNG_B64
from .conftest import Triage


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


@pytest.fixture
def writer() -> _Collecting:
    collecting = _Collecting()
    configure_writers([collecting])
    return collecting


def _decision_events(writer: _Collecting) -> list[Event]:
    return [e for e in writer.events if e.event_type.startswith("decision.")]


def _node_id(writer: _Collecting, name: str) -> str:
    [creation] = [
        e
        for e in writer.events
        if e.event_type == "node.creation" and e.payload["name"] == name
    ]
    return creation.payload["node_id"]


async def test_invocation_and_response_paired_under_the_decision_node(
    make_model, writer
):
    model, _ = make_model()
    node = rt.decision_node("Triage Ticket", model=model, schema=Triage)

    with rt.Session(flow_name="decisions"):
        await rt.call(node, "Help!")

    invocation, response = _decision_events(writer)
    node_id = _node_id(writer, "Triage Ticket")

    assert invocation.event_type == "decision.invocation"
    assert response.event_type == "decision.response"
    assert invocation.payload["decision_id"] == response.payload["decision_id"]
    for event in (invocation, response):
        assert event.payload["parent_node_id"] == node_id
        assert event.payload["spatial_parent_node_id"] == node_id
        assert event.payload["model_name"] == "jev-latest"

    assert invocation.payload["api_base"] == "https://api.typesafe.ai"
    assert invocation.payload["state"] == "Help!"
    assert invocation.payload["questions"]["department"]["type"] == "choice"
    assert invocation.payload["questions"]["department"]["name"] == "department"
    assert invocation.payload["questions"]["frustration"]["levels"][0] == {
        "label": "Calm"
    }

    assert response.payload["reported_model_name"] == "jev-1.13.0"
    assert response.payload["answers"]["is_urgent"] == {"probability": 0.93}
    assert response.payload["input_tokens"] == 296
    assert response.payload["total_cost"] == pytest.approx(296 * 4.2e-08)
    assert response.payload["latency"] > 0


async def test_attachment_state_recorded_without_base64(make_model, writer, tmp_path):
    png = tmp_path / "cat.png"
    png.write_bytes(base64.b64decode(PNG_B64))
    model, fake = make_model(cls=rt.decisions.OpenAIDecisions, model_name="gpt-6-luna")
    node = rt.decision_node("Classify Image", model=model, schema=Triage)
    state = rt.decisions.DecisionState(text="Which animal?", attachments=str(png))

    with rt.Session(flow_name="decisions"):
        result = await rt.call(node, state)

    assert result.structured["is_urgent"].probability == 0.93
    [message] = fake.calls[0]["input"]
    assert message["content"][1]["image_url"].startswith("data:image/png;base64,")
    invocation, _ = _decision_events(writer)
    assert invocation.payload["state"] == {
        "text": "Which animal?",
        "attachments": [str(png)],
    }


async def test_failure_paired_with_invocation(make_model, writer):
    model, _ = make_model(
        litellm.InternalServerError(
            message="boom", llm_provider="typesafe", model="typesafe/jev-latest"
        )
    )
    node = rt.decision_node("Triage Ticket", model=model, schema=Triage)

    with rt.Session(flow_name="decisions", end_on_error=False):
        with pytest.raises(rt.exceptions.DecisionServerError):
            await rt.call(node, "Help!")

    invocation, failure = _decision_events(writer)
    assert failure.event_type == "decision.failure"
    assert failure.payload["decision_id"] == invocation.payload["decision_id"]
    # the event records the model's own error, before the node translates it
    assert failure.payload["exception_name"] == "DecisionProviderServerError"
    assert failure.payload["parent_node_id"] == _node_id(writer, "Triage Ticket")


async def test_direct_aask_inside_a_function_node_is_not_recorded(
    make_model, writer, caplog
):
    # S2 parity: a direct model call isn't recorded; only decision_node calls are
    model, _ = make_model()

    @rt.function_node
    async def triage(text: str) -> str:
        """Triage a ticket.

        Args:
            text: The ticket.
        """
        return str(await model.aask(text, Triage))

    with caplog.at_level(logging.DEBUG):
        with rt.Session(flow_name="decisions"):
            await rt.call(triage, "Help!")

    assert _decision_events(writer) == []
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_decision_node_called_from_a_function_node_is_recorded(
    make_model, writer
):
    model, _ = make_model()
    node = rt.decision_node("Triage Ticket", model=model, schema=Triage)

    @rt.function_node
    async def triage(text: str) -> str:
        """Triage a ticket.

        Args:
            text: The ticket.
        """
        return str(await rt.call(node, text))

    with rt.Session(flow_name="decisions"):
        await rt.call(triage, "Help!")

    invocation, response = _decision_events(writer)
    assert invocation.payload["decision_id"] == response.payload["decision_id"]
    assert {
        invocation.payload["parent_node_id"],
        response.payload["parent_node_id"],
    } == {_node_id(writer, "Triage Ticket")}


async def test_no_events_or_errors_outside_a_run(make_model, writer, caplog):
    model, _ = make_model()
    with caplog.at_level(logging.DEBUG):
        resp = await model.aask("Help!", Triage)

    assert resp.structured["is_urgent"].probability == 0.93
    assert _decision_events(writer) == []
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_no_events_or_errors_in_a_session_outside_a_node(
    make_model, writer, caplog
):
    model, _ = make_model()
    with caplog.at_level(logging.DEBUG):
        with rt.Session(flow_name="decisions"):
            await model.aask("Help!", Triage)

    assert _decision_events(writer) == []
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
