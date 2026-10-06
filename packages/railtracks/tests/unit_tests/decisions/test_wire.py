"""TypeSafe wire mapping: request bodies and response parsing."""

import copy

import pytest
from railtracks.decisions import DecisionProviderResponseError, TypeSafeSchema
from railtracks.decisions.models.typesafe_compatible._wire import (
    build_request,
    parse_response,
)
from railtracks.decisions.models.typesafe_compatible.schema import (
    ChoiceAnswer,
    NoulAnswer,
    ScoreAnswer,
)

from .conftest import TRIAGE_RESPONSE, Triage


class TestBuildRequest:
    def test_choice_matches_documented_request(self):
        # https://docs.typesafe.ai/primitives/choice
        class Routing(TypeSafeSchema):
            department = TypeSafeSchema.Choice(
                instructions="Which team should handle this?",
                criteria={
                    "returns": "Exchanges, wrong or damaged items",
                    "shipping": "Delivery status, delays, lost packages",
                    "billing": "Charges, invoices, payment problems",
                },
            )

        state = (
            "My running shoes arrived in the wrong size. Can I swap them for a size 10?"
        )
        assert build_request("jev-latest", state, Routing) == {
            "state": state,
            "model": "jev-latest",
            "questions": {
                "department": {
                    "type": "choice",
                    "instructions": "Which team should handle this?",
                    "criteria": {
                        "returns": "Exchanges, wrong or damaged items",
                        "shipping": "Delivery status, delays, lost packages",
                        "billing": "Charges, invoices, payment problems",
                    },
                }
            },
        }

    def test_noul_and_score_match_documented_requests(self):
        # https://docs.typesafe.ai/primitives/noul, /primitives/score
        class Support(TypeSafeSchema):
            is_human_escalation = TypeSafeSchema.Noul(
                instructions="Is the customer asking for a human agent?"
            )
            is_repeat_contact = TypeSafeSchema.Noul(
                instructions="Has the customer contacted support about this before?",
                criteria={
                    "true": "Mentions a prior attempt, ticket, or that they have asked before",
                    "false": "No sign of any previous contact",
                },
            )
            bug_severity = TypeSafeSchema.Score(
                instructions="How severe is the reported issue?",
                criteria=[
                    "Cosmetic; no impact to functionality",
                    "Broken or degraded feature, but workaround exists",
                    "Blocking issue; no workaround exists",
                ],
            )

        questions = build_request("jev-latest", "state", Support)["questions"]
        assert questions == {
            "is_human_escalation": {
                "type": "noul",
                "instructions": "Is the customer asking for a human agent?",
            },
            "is_repeat_contact": {
                "type": "noul",
                "instructions": "Has the customer contacted support about this before?",
                "criteria": {
                    "true": "Mentions a prior attempt, ticket, or that they have asked before",
                    "false": "No sign of any previous contact",
                },
            },
            "bug_severity": {
                "type": "score",
                "instructions": "How severe is the reported issue?",
                "criteria": [
                    "Cosmetic; no impact to functionality",
                    "Broken or degraded feature, but workaround exists",
                    "Blocking issue; no workaround exists",
                ],
            },
        }
        assert list(questions) == [
            "is_human_escalation",
            "is_repeat_contact",
            "bug_severity",
        ]

    def test_json_state_passes_through(self):
        state = {"message": "Please help.", "subject": "Duplicate charge"}
        assert build_request("jev-latest", state, Triage)["state"] == state


class TestParseResponse:
    def test_parses_all_three_answer_types(self):
        parsed = parse_response(TRIAGE_RESPONSE, Triage)
        triage = parsed.structured
        assert isinstance(triage, Triage)
        assert triage.is_urgent == NoulAnswer(noul=0.93)
        assert triage.department == ChoiceAnswer(
            choice="technical",
            confidence=0.81,
            probabilities={"billing": 0.02, "technical": 0.88, "sales": 0.1},
        )
        assert triage.frustration == ScoreAnswer(
            score=1.7,
            confidence=0.6,
            probabilities={0: 0.05, 1: 0.2, 2: 0.75},
            legend={0: "Calm", 1: "Frustrated but civil", 2: "Very angry"},
        )

    def test_metadata(self):
        parsed = parse_response(TRIAGE_RESPONSE, Triage)
        assert parsed.reported_model_name == "jev-1.13.0"
        assert parsed.provider is None
        assert parsed.input_tokens == 296
        assert parsed.output_tokens == 20
        assert parsed.raw == TRIAGE_RESPONSE

    def test_provider_and_missing_usage_tolerated(self):
        body = copy.deepcopy(TRIAGE_RESPONSE)
        del body["usage"]
        del body["model"]
        body["provider"] = "TypeSafe"
        parsed = parse_response(body, Triage)
        assert parsed.provider == "TypeSafe"
        assert parsed.reported_model_name is None
        assert parsed.input_tokens is None

    def test_reported_cost_parsed(self):
        # OpenRouter reports what it billed in usage.cost
        body = copy.deepcopy(TRIAGE_RESPONSE)
        body["usage"]["cost"] = 1.7556e-05
        assert parse_response(body, Triage).reported_cost == 1.7556e-05
        body["usage"]["cost"] = 0
        assert parse_response(body, Triage).reported_cost == 0.0

    @pytest.mark.parametrize("cost", [None, "0.01", True, -1.0])
    def test_unusable_reported_cost_ignored(self, cost):
        body = copy.deepcopy(TRIAGE_RESPONSE)
        body["usage"]["cost"] = cost
        assert parse_response(body, Triage).reported_cost is None

    def test_no_reported_cost(self):
        assert parse_response(TRIAGE_RESPONSE, Triage).reported_cost is None

    def test_unrequested_answers_ignored(self):
        body = copy.deepcopy(TRIAGE_RESPONSE)
        body["answers"]["extra"] = {"type": "noul", "noul": 0.1}
        assert parse_response(body, Triage).structured.is_urgent.noul == 0.93

    @pytest.mark.parametrize(
        "mutate, field",
        [
            (lambda b: b.pop("answers"), "answers"),
            (lambda b: b["answers"].pop("department"), "answers.department"),
            (
                lambda b: b["answers"]["department"].pop("probabilities"),
                "answers.department.probabilities",
            ),
            (lambda b: b["answers"]["is_urgent"].pop("noul"), "answers.is_urgent.noul"),
            (
                lambda b: b["answers"]["is_urgent"].update(type="score"),
                "answers.is_urgent.type",
            ),
        ],
    )
    def test_malformed_response_names_the_field(self, mutate, field):
        body = copy.deepcopy(TRIAGE_RESPONSE)
        mutate(body)
        with pytest.raises(
            DecisionProviderResponseError, match=field.replace(".", r"\.")
        ):
            parse_response(body, Triage)

    def test_non_object_body_rejected(self):
        with pytest.raises(DecisionProviderResponseError):
            parse_response(["not", "an", "object"], Triage)
