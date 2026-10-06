"""decision_node: a Tool node over model.aask, usable from Flow, call_batch and agents."""

import json

import httpx
import pytest
import railtracks as rt
import railtracks.context.central as central
from railtracks.built_nodes.decisions import DecisionResponse
from railtracks.decisions import (
    DecisionProviderAuthenticationError,
    DecisionProviderConnectionError,
    DecisionProviderError,
    DecisionProviderRateLimitError,
    DecisionProviderRequestError,
    DecisionProviderResponseError,
    DecisionProviderServerError,
    DecisionProviderTimeoutError,
    NoulAnswer,
)
from railtracks.decisions.schema import DecisionQuestion, DecisionSchema
from railtracks.exceptions import (
    DecisionAuthenticationError,
    DecisionModelError,
    DecisionRateLimitError,
    DecisionRequestError,
    DecisionResponseError,
    DecisionServerError,
    DecisionTimeoutError,
    NodeCreationError,
)
from railtracks.llm import ToolCall
from railtracks.observability import Event, configure, configure_writers
from railtracks.utils.json.encoder import RTJSONEncoder

from .conftest import Triage, ok


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


def _failing_on(state: str):
    """A handler that answers every request except the one whose state is ``state``."""

    def handler(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content)["state"] == state:
            return httpx.Response(500, text="boom")
        return ok()

    return handler


def _model_with(handler) -> rt.decisions.TypeSafeAI:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return rt.decisions.TypeSafeAI("jev-latest", api_key="k", http_client=client)


# ================= Construction =================


class TestConstruction:
    def test_tool_node_named_like_agent_node(self, make_model):
        model, _ = make_model()
        node = rt.decision_node("Triage Ticket", model=model, schema=Triage)

        assert node.name() == "Triage Ticket"
        assert node.type() == "Tool"
        tool = node.tool_info()
        assert tool.name == "Triage_Ticket"
        [param] = tool.parameters
        assert param.name == "state"
        assert param.required

    def test_name_defaults_to_schema_name(self, make_model):
        model, _ = make_model()
        assert rt.decision_node(model=model, schema=Triage).name() == "Triage"

    def test_default_detail_lists_each_question(self, make_model):
        model, _ = make_model()
        detail = rt.decision_node(model=model, schema=Triage).tool_info().detail
        for name, instructions in [
            ("is_urgent", "The message conveys urgency"),
            ("department", "Which team should handle this"),
            ("frustration", "How frustrated the customer is"),
        ]:
            assert f"{name}: {instructions}" in detail

    def test_custom_description(self, make_model):
        model, _ = make_model()
        node = rt.decision_node(model=model, schema=Triage, description="Triage it.")
        assert node.tool_info().detail == "Triage it."

    @pytest.mark.parametrize("name", ["", "   "])
    def test_blank_name_rejected(self, make_model, name):
        model, _ = make_model()
        with pytest.raises(NodeCreationError, match="name"):
            rt.decision_node(name, model=model, schema=Triage)

    def test_schema_from_another_vendor_rejected(self, make_model):
        class OtherQuestion(DecisionQuestion[NoulAnswer]):
            answer_type = NoulAnswer

        class OtherSchema(DecisionSchema, abstract=True):
            _question_type = OtherQuestion

        class Other(OtherSchema):
            q = OtherQuestion(instructions="x")

        model, _ = make_model()
        with pytest.raises(NodeCreationError, match="TypeSafeSchema"):
            rt.decision_node(model=model, schema=Other)

    def test_abstract_schema_rejected(self, make_model):
        model, _ = make_model()
        with pytest.raises(NodeCreationError, match="subclass"):
            rt.decision_node(model=model, schema=rt.decisions.TypeSafeSchema)


# ================= Invocation =================


def test_flow_invoke_returns_the_decision_response(make_model):
    model, recorder = make_model()
    node = rt.decision_node("Triage Ticket", model=model, schema=Triage)

    result = rt.Flow(name="Ticket Triage", entry_point=node).invoke("Help!")

    assert isinstance(result, DecisionResponse)
    assert result.structured.department.choice == "technical"
    assert recorder.body()["state"] == "Help!"


async def test_call_passes_json_state_through(make_model):
    model, recorder = make_model()
    node = rt.decision_node(model=model, schema=Triage)

    with rt.Session(flow_name="decisions"):
        result = await rt.call(node, {"subject": "Duplicate charge"})

    assert result.structured.is_urgent.noul == 0.93
    assert recorder.body()["state"] == {"subject": "Duplicate charge"}


async def test_call_batch_preserves_order_and_returns_exceptions():
    node = rt.decision_node(model=_model_with(_failing_on("b")), schema=Triage)

    with rt.Session(flow_name="decisions", end_on_error=False):
        results = await rt.call_batch(node, ["a", "b", "c"])

    assert isinstance(results[0], DecisionResponse)
    assert isinstance(results[1], DecisionServerError)
    assert isinstance(results[2], DecisionResponse)


@pytest.mark.parametrize(
    "failure, node_error, provider_error",
    [
        (
            httpx.Response(401, text="no"),
            DecisionAuthenticationError,
            DecisionProviderAuthenticationError,
        ),
        (
            httpx.Response(429, text="slow"),
            DecisionRateLimitError,
            DecisionProviderRateLimitError,
        ),
        (httpx.ReadTimeout("slow"), DecisionTimeoutError, DecisionProviderTimeoutError),
        (
            httpx.ConnectError("refused"),
            DecisionTimeoutError,
            DecisionProviderConnectionError,
        ),
        (
            httpx.Response(503, text="down"),
            DecisionServerError,
            DecisionProviderServerError,
        ),
        (
            httpx.Response(200, text="<html>"),
            DecisionResponseError,
            DecisionProviderResponseError,
        ),
    ],
)
def test_provider_errors_become_decision_errors_at_the_node(
    make_model, failure, node_error, provider_error
):
    model, _ = make_model(failure)
    node = rt.decision_node(model=model, schema=Triage)

    with pytest.raises(node_error) as info:
        rt.Flow(name="decisions", entry_point=node).invoke("Help!")

    assert isinstance(info.value, DecisionModelError)
    assert type(info.value.__cause__) is provider_error
    assert isinstance(info.value.__cause__, DecisionProviderError)
    assert info.value.reason == info.value.__cause__.reason


def test_request_error_keeps_body_and_notes(make_model):
    model, _ = make_model(httpx.Response(422, text='{"detail": "bad state"}'))
    node = rt.decision_node(model=model, schema=Triage)

    with pytest.raises(DecisionRequestError) as info:
        rt.Flow(name="decisions", entry_point=node).invoke("Help!")

    assert info.value.body == '{"detail": "bad state"}'
    assert isinstance(info.value.__cause__, DecisionProviderRequestError)
    assert info.value.notes == info.value.__cause__.notes


def test_agent_reads_the_compact_str(make_model, mock_llm):
    model, recorder = make_model()
    node = rt.decision_node("Triage Ticket", model=model, schema=Triage)
    llm = mock_llm(
        requested_tool_calls=[
            ToolCall(
                name="Triage_Ticket",
                identifier="tc_1",
                arguments={"state": "Our checkout is down!"},
            )
        ]
    )
    agent = rt.agent_node("Support Agent", llm=llm, tool_nodes=[node])

    result = rt.Flow(name="Support", entry_point=agent).invoke("Triage this")

    assert recorder.body()["state"] == "Our checkout is down!"
    assert (
        "is_urgent: yes 0.93 | department: technical 0.88 | frustration: 1.7/2"
        in result.text
    )


async def test_node_response_event_stores_the_structured_dict(make_model):
    writer = _Collecting()
    configure_writers([writer])
    model, _ = make_model()
    node = rt.decision_node("Triage Ticket", model=model, schema=Triage)

    with rt.Session(flow_name="decisions"):
        await rt.call(node, "Help!")

    [event] = [e for e in writer.events if e.event_type == "node.response"]
    encoded = json.loads(json.dumps(event.payload["response"], cls=RTJSONEncoder))
    assert encoded["structured"]["department"]["choice"] == "technical"
    assert encoded["model_name"] == "jev-1.13.0"
