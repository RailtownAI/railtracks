"""DecisionResponse: the compact str an agent reads, and JSON encoding."""

import json

from railtracks.built_nodes.decisions import DecisionResponse
from railtracks.built_nodes.decisions.typesafe._wire import parse_response
from railtracks.utils.json.encoder import RTJSONEncoder

from .conftest import TRIAGE_RESPONSE, Triage


def _response(**overrides) -> DecisionResponse[Triage]:
    fields = {
        "structured": parse_response(TRIAGE_RESPONSE, Triage).structured,
        "model_name": "jev-1.13.0",
        "provider": None,
        "input_tokens": 296,
        "output_tokens": 20,
        "latency": 0.21,
        "cost": 1.2432e-05,
        "raw": TRIAGE_RESPONSE,
        **overrides,
    }
    return DecisionResponse(**fields)


def test_str_one_segment_per_question_in_definition_order():
    assert (
        str(_response())
        == "is_urgent: yes 0.93 | department: technical 0.88 | frustration: 1.7/2"
    )


def test_str_noul_below_half_is_no():
    body = json.loads(json.dumps(TRIAGE_RESPONSE))
    body["answers"]["is_urgent"]["noul"] = 0.12
    resp = _response(structured=parse_response(body, Triage).structured)
    assert str(resp).startswith("is_urgent: no 0.12 | ")


def test_encodes_to_a_structured_dict():
    encoded = json.loads(json.dumps(_response(), cls=RTJSONEncoder))
    assert encoded == {
        "structured": {
            "is_urgent": {"noul": 0.93},
            "department": {
                "choice": "technical",
                "confidence": 0.81,
                "probabilities": {"billing": 0.02, "technical": 0.88, "sales": 0.1},
            },
            "frustration": {
                "score": 1.7,
                "confidence": 0.6,
                "probabilities": {"0": 0.05, "1": 0.2, "2": 0.75},
                "legend": {"0": "Calm", "1": "Frustrated but civil", "2": "Very angry"},
            },
        },
        "model_name": "jev-1.13.0",
        "provider": None,
        "input_tokens": 296,
        "output_tokens": 20,
        "latency": 0.21,
        "cost": 1.2432e-05,
    }
