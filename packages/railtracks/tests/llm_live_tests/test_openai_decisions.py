"""Live calls to OpenAI's Decisions API (gpt-6-luna).

Each call costs about $0.00004 (input tokens only). Skipped without OPENAI_API_KEY.
"""

import base64
import os
import struct
import zlib

import pytest
import railtracks as rt

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)

MODEL = "gpt-6-luna"
OpenAISchema = rt.decisions.OpenAISchema


class Triage(OpenAISchema):
    is_urgent = OpenAISchema.Predicate(instructions="The message conveys urgency")
    department = OpenAISchema.Choice(
        instructions="Which team should handle this",
        choices={
            "billing": "Charges, refunds, invoices, or plan changes",
            "technical": "Bugs, outages, errors, or integration problems",
            "sales": "Pricing questions, upgrades, or new purchases",
        },
    )
    frustration = OpenAISchema.Score(
        instructions="How frustrated the customer is",
        levels=["Calm", "Frustrated but civil", "Very angry"],
    )


OUTAGE = (
    "Your API has returned 502s for an hour and our checkout is down. FIX THIS NOW."
)
BILLING = "I was charged twice for my March invoice. Please refund the duplicate."


async def test_aask_parses_every_answer_type_and_the_metadata():
    resp = await rt.decisions.OpenAIDecisions(MODEL).aask(OUTAGE, Triage)

    assert resp.structured.department.choice == "technical"
    assert resp.structured.is_urgent.probability > 0.5
    assert set(resp.structured.frustration.legend) == {0, 1, 2}
    assert resp.model_name.startswith(MODEL)
    assert resp.provider == "openai"
    assert resp.input_tokens and resp.input_tokens > 0
    assert resp.cost and resp.cost > 0  # catalog input price; output never billed


async def test_json_state():
    state = {"subject": "Duplicate charge", "body": BILLING}
    resp = await rt.decisions.OpenAIDecisions(MODEL).aask(state, Triage)
    assert resp.structured.department.choice == "billing"


def test_decision_node_in_a_flow():
    node = rt.decision_node(
        "Triage Ticket", model=rt.decisions.OpenAIDecisions(MODEL), schema=Triage
    )
    result = rt.Flow(name="Live OpenAI Triage", entry_point=node).invoke(OUTAGE)
    assert result.structured.department.choice == "technical"


async def test_rejected_key_is_an_auth_error():
    model = rt.decisions.OpenAIDecisions(MODEL, api_key="sk-not-a-real-key")
    with pytest.raises(rt.decisions.DecisionProviderAuthenticationError):
        await model.aask(OUTAGE, Triage)


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


class Colour(OpenAISchema):
    is_red = OpenAISchema.Predicate(instructions="The image is a solid red square")
    colour = OpenAISchema.Choice(
        instructions="The main colour of the image", choices=["red", "green", "blue"]
    )


@pytest.mark.parametrize("rgb, colour", [((255, 0, 0), "red"), ((0, 0, 255), "blue")])
async def test_image_input(rgb, colour):
    image = base64.b64encode(_solid_png(rgb)).decode("ascii")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Look at this image."},
                {"type": "input_image", "image_url": f"data:image/png;base64,{image}"},
            ],
        }
    ]
    resp = await rt.decisions.OpenAIDecisions(MODEL).aask(messages, Colour)
    assert resp.structured.colour.choice == colour
    assert (resp.structured.is_red.probability > 0.5) == (colour == "red")
