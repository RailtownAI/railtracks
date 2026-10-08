"""The OpenAI-shape wire mapping litellm.adecisions takes and returns."""

import copy
import json

import pytest
from railtracks.decisions import (
    ChoiceAnswer,
    DecisionProviderRefusalError,
    DecisionProviderResponseError,
    DecisionSchema,
    PredicateAnswer,
    ScoreAnswer,
)
from railtracks.decisions.transport._wire import (
    describe_questions,
    parse_response,
    questions_to_wire,
    to_input,
)

from .conftest import TRIAGE_BODY, Triage, respond

TRIAGE_QUESTIONS = [
    {
        "type": "predicate",
        "name": "is_urgent",
        "instructions": "The message conveys urgency",
    },
    {
        "type": "choice",
        "name": "department",
        "instructions": "Which team should handle this",
        "choices": [
            {
                "value": "billing",
                "description": "Charges, refunds, invoices, or plan changes",
            },
            {
                "value": "technical",
                "description": "Bugs, outages, errors, or integration problems",
            },
            {
                "value": "sales",
                "description": "Pricing questions, upgrades, or new purchases",
            },
        ],
    },
    {
        "type": "score",
        "name": "frustration",
        "instructions": "How frustrated the customer is",
        "levels": [
            {"label": "Calm"},
            {"label": "Frustrated but civil"},
            {"label": "Very angry"},
        ],
    },
]


class TestRequest:
    def test_questions_in_the_openai_shape_with_names(self):
        assert questions_to_wire(Triage) == TRIAGE_QUESTIONS

    def test_list_choices_and_mapping_levels(self):
        class Routing(DecisionSchema):
            team = DecisionSchema.Choice(instructions="Team", choices=["a", "b"])
            severity = DecisionSchema.Score(
                instructions="Severity", levels={"Low": "Cosmetic", "High": "Outage"}
            )

        assert questions_to_wire(Routing) == [
            {
                "type": "choice",
                "name": "team",
                "instructions": "Team",
                "choices": [{"value": "a"}, {"value": "b"}],
            },
            {
                "type": "score",
                "name": "severity",
                "instructions": "Severity",
                "levels": [
                    {"label": "Low", "description": "Cosmetic"},
                    {"label": "High", "description": "Outage"},
                ],
            },
        ]

    def test_describe_questions_keys_the_wire_questions_by_name(self):
        described = describe_questions(Triage)
        assert list(described) == ["is_urgent", "department", "frustration"]
        assert list(described.values()) == TRIAGE_QUESTIONS

    def test_text_input_as_is(self):
        assert to_input("My checkout is down.") == "My checkout is down."

    def test_json_object_becomes_text(self):
        state = {"subject": "Duplicate charge", "body": "Charged twice"}
        assert to_input(state) == json.dumps(state)

    def test_user_messages_pass_through(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Inspect this photo."},
                    {"type": "input_image", "image_url": "data:image/png;base64,AAAA"},
                ],
            }
        ]
        assert to_input(messages) is messages

    @pytest.mark.parametrize(
        "state",
        [[{"sku": 1}, {"sku": 2}], [], [{"role": "assistant", "content": "hi"}]],
        ids=["records", "empty", "assistant-message"],
    )
    def test_json_array_that_is_not_user_messages_becomes_text(self, state):
        assert to_input(state) == json.dumps(state)


class TestParseResponse:
    def test_parses_all_three_answer_types(self):
        triage = parse_response(respond(), Triage).structured
        assert triage.is_urgent == PredicateAnswer(probability=0.93)
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
        reply = parse_response(respond(), Triage)
        assert reply.reported_model_name == "jev-1.13.0"
        assert reply.input_tokens == 296
        assert reply.output_tokens == 20
        assert reply.provider is None
        assert reply.reported_cost is None  # the transport reads the cost
        assert reply.raw["usage"]["total_tokens"] == 316
        assert reply.raw["answers"][0]["name"] == "is_urgent"

    def test_answers_matched_by_name_not_position(self):
        body = copy.deepcopy(TRIAGE_BODY)
        body["answers"].reverse()
        assert parse_response(respond(body), Triage).structured.is_urgent == (
            PredicateAnswer(probability=0.93)
        )

    def test_answers_without_names_matched_by_position(self):
        body = copy.deepcopy(TRIAGE_BODY)
        for answer in body["answers"]:
            answer["name"] = None
        reply = parse_response(respond(body), Triage)
        assert reply.structured.department.choice == "technical"

    def test_refusal_raises_with_the_other_answers(self):
        body = copy.deepcopy(TRIAGE_BODY)
        body["answers"][1] = {"type": "refusal", "name": "department"}
        with pytest.raises(DecisionProviderRefusalError) as info:
            parse_response(respond(body), Triage)
        assert info.value.refused == ["department"]
        assert set(info.value.answers) == {"is_urgent", "frustration"}
        assert "department" in info.value.reason

    def test_every_question_refused(self):
        body = copy.deepcopy(TRIAGE_BODY)
        body["answers"] = [
            {"type": "refusal", "name": name}
            for name in ("is_urgent", "department", "frustration")
        ]
        with pytest.raises(DecisionProviderRefusalError) as info:
            parse_response(respond(body), Triage)
        assert info.value.refused == ["is_urgent", "department", "frustration"]
        assert info.value.answers == {}

    def test_dict_body_accepted(self):
        reply = parse_response(copy.deepcopy(TRIAGE_BODY), Triage)
        assert reply.structured.is_urgent.probability == 0.93

    @pytest.mark.parametrize(
        "mutate, field",
        [
            (lambda b: b.pop("answers"), "answers"),
            (lambda b: b["answers"].pop(0), "answers.is_urgent"),
            (
                lambda b: b["answers"][0].pop("probability"),
                "answers.is_urgent.probability",
            ),
            (lambda b: b["answers"][0].update(type="score"), "answers.is_urgent.type"),
            (
                lambda b: b["answers"][1]["probabilities"][0].pop("value"),
                "answers.department.probabilities",
            ),
        ],
        ids=[
            "no-answers",
            "missing-answer",
            "missing-field",
            "wrong-type",
            "bad-probabilities",
        ],
    )
    def test_malformed_response_names_the_field(self, mutate, field):
        body = copy.deepcopy(TRIAGE_BODY)
        mutate(body)
        with pytest.raises(
            DecisionProviderResponseError, match=field.replace(".", r"\.")
        ):
            parse_response(body, Triage)

    def test_non_object_body_rejected(self):
        with pytest.raises(DecisionProviderResponseError, match="<body>"):
            parse_response(["not", "an", "object"], Triage)
