"""Live decision calls through ``litellm.adecisions``, one run per vendor.

TypeSafe (``jev-latest``), OpenRouter (``typesafe/jev-1.13``) and OpenAI
(``gpt-6-luna``). Each call costs about $0.00002 to $0.00004. A vendor's tests are
skipped when its key (TYPESAFE_API_KEY, OPENROUTER_API_KEY, OPENAI_API_KEY) is unset.
"""

import base64
import os
import struct
import zlib
from dataclasses import dataclass

import litellm
import pytest
import railtracks as rt
import railtracks.context.central as central
from railtracks.decisions import (
    Choice,
    DecisionModel,
    DecisionSchema,
    DecisionState,
    Predicate,
    Score,
)
from railtracks.decisions.transport._litellm import LiteLLMDecisionModel
from railtracks.observability import Event, configure, configure_writers


@dataclass(frozen=True)
class Vendor:
    model_class: type[LiteLLMDecisionModel]
    model_name: str
    key_env: str
    reported_prefix: str
    """What the reported model name starts with; hosts report a dated snapshot."""


TYPESAFE = Vendor(rt.decisions.TypeSafeAI, "jev-latest", "TYPESAFE_API_KEY", "jev-")
OPENROUTER = Vendor(
    rt.decisions.OpenRouterAI,
    "typesafe/jev-1.13",
    "OPENROUTER_API_KEY",
    "typesafe/jev-1.13",
)
OPENAI = Vendor(
    rt.decisions.OpenAIDecisions, "gpt-6-luna", "OPENAI_API_KEY", "gpt-6-luna"
)


def _param(vendor: Vendor):
    return pytest.param(
        vendor,
        id=vendor.model_class.provider_prefix,
        marks=pytest.mark.skipif(
            not os.environ.get(vendor.key_env), reason=f"{vendor.key_env} not set"
        ),
    )


ALL_VENDORS = [_param(TYPESAFE), _param(OPENROUTER), _param(OPENAI)]


is_urgent = Predicate(name="is_urgent", instructions="The message conveys urgency")
department = Choice(
    name="department",
    instructions="Which team should handle this",
    choices={
        "billing": "Charges, refunds, invoices, or plan changes",
        "technical": "Bugs, outages, errors, or integration problems",
        "sales": "Pricing questions, upgrades, or new purchases",
    },
)
frustration = Score(
    name="frustration",
    instructions="How frustrated the customer is",
    levels=["Calm", "Frustrated but civil", "Very angry"],
)
Triage = DecisionSchema(predicate=[is_urgent], choice=[department], score=[frustration])


BILLING = "I was charged twice for my March invoice. Please refund the duplicate."
OUTAGE = (
    "Your API has returned 502s for an hour and our checkout is down. FIX THIS NOW."
)


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


def _model(vendor: Vendor, **kwargs) -> DecisionModel:
    return vendor.model_class(vendor.model_name, **kwargs)


@pytest.mark.parametrize("vendor", ALL_VENDORS)
async def test_aask_parses_every_answer_type_and_the_metadata(vendor):
    resp = await _model(vendor).aask(OUTAGE, Triage)

    assert resp.structured[department].choice == "technical"
    assert set(resp.structured[department].probabilities) == {
        "billing",
        "technical",
        "sales",
    }
    assert resp.structured[is_urgent].probability > 0.5
    assert resp.structured[frustration].legend == {
        0: "Calm",
        1: "Frustrated but civil",
        2: "Very angry",
    }
    assert 0.0 <= resp.structured[frustration].score <= 2.0
    assert resp.model_name.startswith(vendor.reported_prefix)
    assert resp.requested_model_name == vendor.model_name
    assert resp.provider == vendor.model_class.provider_name
    assert resp.input_tokens and resp.input_tokens > 0
    assert resp.cost and resp.cost > 0  # litellm's response_cost
    assert resp.latency > 0


@pytest.mark.parametrize("vendor", ALL_VENDORS)
async def test_json_state(vendor):
    state = {"subject": "Duplicate charge", "body": BILLING}
    resp = await _model(vendor).aask(state, Triage)
    assert resp.structured[department].choice == "billing"


@pytest.mark.parametrize("vendor", ALL_VENDORS)
def test_decision_node_in_a_flow_records_paired_events(vendor):
    writer = _Collecting()
    configure_writers([writer])
    node = rt.decision_node("Triage Ticket", model=_model(vendor), schema=Triage)

    result = rt.Flow(name="Live Triage", entry_point=node).invoke(OUTAGE)

    assert result.structured[department].choice == "technical"
    invocation, response = [
        e for e in writer.events if e.event_type.startswith("decision.")
    ]
    assert invocation.event_type == "decision.invocation"
    assert response.event_type == "decision.response"
    assert invocation.payload["decision_id"] == response.payload["decision_id"]
    assert response.payload["total_cost"] == result.cost


@pytest.mark.parametrize("vendor", ALL_VENDORS)
async def test_call_batch_preserves_order(vendor):
    node = rt.decision_node(model=_model(vendor), schema=Triage)

    with rt.Session(flow_name="Live Batch"):
        results = await rt.call_batch(node, [BILLING, OUTAGE])

    assert [r.structured[department].choice for r in results] == [
        "billing",
        "technical",
    ]


@pytest.mark.parametrize("vendor", ALL_VENDORS)
async def test_rejected_key_is_an_auth_error_and_not_retried(vendor, monkeypatch):
    calls: list[str] = []
    real = litellm.adecisions

    async def counting(*args, **kwargs):
        calls.append(kwargs["model"])
        return await real(*args, **kwargs)

    monkeypatch.setattr(litellm, "adecisions", counting)
    model = _model(
        vendor,
        api_key="sk-not-a-real-key",
        retry_approach=rt.llm.retries.FixedRetry(max_tries=3, delay=0.0),
    )

    with pytest.raises(rt.decisions.DecisionProviderAuthenticationError):
        await model.aask(OUTAGE, Triage)

    assert len(calls) == 1


def _solid_png(rgb: tuple[int, int, int], size: int = 16) -> bytes:
    """A tiny solid-colour PNG, built in memory so the test needs no fixture file."""
    rows = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + tag + data + crc

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


is_red = Predicate(name="is_red", instructions="The image is a solid red square")
colour = Choice(
    name="colour",
    instructions="The main colour of the image",
    choices=["red", "green", "blue"],
)
Colour = DecisionSchema(predicate=[is_red], choice=[colour])


@pytest.mark.parametrize("vendor", [_param(OPENAI)])
async def test_image_input(vendor):
    image = base64.b64encode(_solid_png((0, 0, 255))).decode("ascii")
    state = DecisionState(text="Look at this image.", attachments=image)
    resp = await _model(vendor).aask(state, Colour)
    assert resp.structured[colour].choice == "blue"
    assert resp.structured[is_red].probability < 0.5
