"""OpenAI's Decisions API: OpenAISchema, the /v1/decisions wire format and the host."""

import copy
import json

import httpx
import litellm
import pytest
import railtracks as rt
from railtracks.decisions import (
    ChoiceAnswer,
    DecisionProviderAuthenticationError,
    DecisionProviderRefusalError,
    DecisionProviderRequestError,
    DecisionProviderResponseError,
    OpenAIDecisions,
    OpenAISchema,
    PredicateAnswer,
    SchemaDefinitionError,
    ScoreAnswer,
    TypeSafeSchema,
)
from railtracks.decisions.models.openai_decisions._wire import (
    build_request,
    parse_response,
)

from .conftest import Recorder


class Triage(OpenAISchema):
    is_urgent = OpenAISchema.Predicate(instructions="The message conveys urgency")
    department = OpenAISchema.Choice(
        instructions="Which team should handle this",
        choices={
            "billing": "Charges or refunds",
            "technical": "Bugs or outages",
            "sales": "Pricing",
        },
    )
    frustration = OpenAISchema.Score(
        instructions="How frustrated the customer is",
        levels=["Calm", "Frustrated but civil", "Very angry"],
    )


# Captured from POST https://api.openai.com/v1/decisions on 2026-10-07.
LIVE_RESPONSE = {
    "model": "gpt-6-luna",
    "answers": [
        {"type": "predicate", "name": "is_urgent", "probability": 0.99},
        {
            "type": "choice",
            "name": "department",
            "choice": "technical",
            "probabilities": [
                {"value": "billing", "probability": 0.0},
                {"value": "technical", "probability": 1.0},
                {"value": "sales", "probability": 0.0},
            ],
            "confidence": 1.0,
        },
        {
            "type": "score",
            "name": "frustration",
            "score": 1.08,
            "probabilities": [
                {"value": 0, "label": "Calm", "probability": 0.0},
                {"value": 1, "label": "Frustrated but civil", "probability": 0.92},
                {"value": 2, "label": "Very angry", "probability": 0.08},
            ],
            "confidence": 0.88,
        },
    ],
    "usage": {
        "input_tokens": 398,
        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        "output_tokens": 0,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": 398,
    },
}


@pytest.fixture(autouse=True)
def _no_openai_env(monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


def _model(*responses, **kwargs) -> tuple[OpenAIDecisions, Recorder]:
    recorder = Recorder(*(responses or (httpx.Response(200, json=LIVE_RESPONSE),)))
    client = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    kwargs.setdefault("api_key", "sk-test")
    return OpenAIDecisions("gpt-6-luna", http_client=client, **kwargs), recorder


# ================= Schema =================


class TestSchema:
    def test_questions_in_definition_order(self):
        assert list(Triage.__questions__) == ["is_urgent", "department", "frustration"]

    def test_choices_and_levels_accept_a_list_or_a_mapping(self):
        choice = OpenAISchema.Choice(instructions="x", choices=["a", "b"])
        score = OpenAISchema.Score(
            instructions="x", levels={"Low": "Fine", "High": "Bad"}
        )
        assert choice.choices == {"a": None, "b": None}
        assert score.levels == {"Low": "Fine", "High": "Bad"}

    @pytest.mark.parametrize(
        "make",
        [
            lambda: OpenAISchema.Predicate(instructions=" "),
            lambda: OpenAISchema.Choice(instructions="x", choices=["only"]),
            lambda: OpenAISchema.Choice(instructions="x", choices=["a", "a"]),
            lambda: OpenAISchema.Choice(instructions="x", choices=["a", ""]),
            lambda: OpenAISchema.Choice(instructions="x", choices="ab"),
            lambda: OpenAISchema.Score(instructions="x", levels=["one"]),
            lambda: OpenAISchema.Score(instructions="x", levels=["Low", "Low"]),
        ],
        ids=[
            "blank-instructions",
            "one-choice",
            "duplicate-choice",
            "blank-choice",
            "string-not-list",
            "one-level",
            "duplicate-level",
        ],
    )
    def test_invalid_questions_rejected(self, make):
        with pytest.raises(SchemaDefinitionError):
            make()

    def test_typesafe_questions_rejected_on_an_openai_schema(self):
        with pytest.raises(SchemaDefinitionError):
            type(
                "Mixed",
                (OpenAISchema,),
                {"q": TypeSafeSchema.Noul(instructions="x")},
            )

    def test_predicate_answer_str(self):
        assert str(PredicateAnswer(probability=0.99)) == "yes 0.99"
        assert str(PredicateAnswer(probability=0.12)) == "no 0.12"


# ================= Wire =================


class TestBuildRequest:
    def test_matches_the_documented_shape(self):
        body = build_request("gpt-6-luna", "My checkout is down.", Triage)
        assert body == {
            "model": "gpt-6-luna",
            "input": "My checkout is down.",
            "questions": [
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
                        {"value": "billing", "description": "Charges or refunds"},
                        {"value": "technical", "description": "Bugs or outages"},
                        {"value": "sales", "description": "Pricing"},
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
            ],
        }

    def test_json_state_becomes_text(self):
        state = {"subject": "Duplicate charge", "body": "Charged twice"}
        assert build_request("gpt-6-luna", state, Triage)["input"] == json.dumps(state)

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
        assert build_request("gpt-6-luna", messages, Triage)["input"] == messages

    def test_json_array_that_is_not_messages_becomes_text(self):
        state = [{"sku": 1}, {"sku": 2}]
        assert build_request("gpt-6-luna", state, Triage)["input"] == json.dumps(state)


class TestParseResponse:
    def test_parses_the_live_response(self):
        reply = parse_response(LIVE_RESPONSE, Triage)
        triage = reply.structured
        assert triage.is_urgent == PredicateAnswer(probability=0.99)
        assert triage.department == ChoiceAnswer(
            choice="technical",
            confidence=1.0,
            probabilities={"billing": 0.0, "technical": 1.0, "sales": 0.0},
        )
        assert triage.frustration == ScoreAnswer(
            score=1.08,
            confidence=0.88,
            probabilities={0: 0.0, 1: 0.92, 2: 0.08},
            legend={0: "Calm", 1: "Frustrated but civil", 2: "Very angry"},
        )
        assert reply.reported_model_name == "gpt-6-luna"
        assert reply.input_tokens == 398
        assert reply.output_tokens == 0
        assert reply.reported_cost is None

    def test_answers_without_names_are_matched_by_position(self):
        body = copy.deepcopy(LIVE_RESPONSE)
        for answer in body["answers"]:
            del answer["name"]
        assert parse_response(body, Triage).structured.department.choice == "technical"

    def test_refusal_raises_with_the_other_answers(self):
        body = copy.deepcopy(LIVE_RESPONSE)
        body["answers"][1] = {"type": "refusal", "name": "department"}
        with pytest.raises(DecisionProviderRefusalError) as info:
            parse_response(body, Triage)
        assert info.value.refused == ["department"]
        assert set(info.value.answers) == {"is_urgent", "frustration"}
        assert "department" in info.value.reason

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
        body = copy.deepcopy(LIVE_RESPONSE)
        mutate(body)
        with pytest.raises(
            DecisionProviderResponseError, match=field.replace(".", r"\.")
        ):
            parse_response(body, Triage)


# ================= Host =================


class TestOpenAIDecisions:
    async def test_posts_to_v1_decisions(self):
        model, recorder = _model()
        resp = await model.aask("My checkout is down.", Triage)
        request = recorder.requests[0]
        assert str(request.url) == "https://api.openai.com/v1/decisions"
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert recorder.body()["questions"][0]["type"] == "predicate"
        assert resp.provider == "openai"
        assert resp.model_name == "gpt-6-luna"

    async def test_key_and_base_url_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://eu.api.openai.com/v1/")
        model, recorder = _model(api_key=None)
        await model.aask("x", Triage)
        assert str(recorder.requests[0].url) == "https://eu.api.openai.com/v1/decisions"
        assert recorder.requests[0].headers["Authorization"] == "Bearer sk-env"

    async def test_requires_a_key(self):
        model, recorder = _model(api_key=None)
        with pytest.raises(DecisionProviderAuthenticationError, match="OPENAI_API_KEY"):
            await model.aask("x", Triage)
        assert recorder.requests == []

    async def test_cost_is_input_tokens_only(self, monkeypatch):
        # litellm lists gpt-6-luna at chat prices; Decisions bills no output tokens
        monkeypatch.setitem(
            litellm.model_cost,
            "gpt-6-luna",
            {"input_cost_per_token": 1e-07, "output_cost_per_token": 5e-07},
        )
        body = copy.deepcopy(LIVE_RESPONSE)
        body["usage"]["output_tokens"] = 100
        model, _ = _model(httpx.Response(200, json=body))
        resp = await model.aask("x", Triage)
        assert resp.cost == pytest.approx(398 * 1e-07)

    async def test_refusal_is_not_retried(self):
        body = copy.deepcopy(LIVE_RESPONSE)
        body["answers"][0] = {"type": "refusal", "name": "is_urgent"}
        model, recorder = _model(
            httpx.Response(200, json=body),
            retry_approach=rt.llm.retries.FixedRetry(max_tries=3, delay=0.0),
        )
        with pytest.raises(DecisionProviderRefusalError):
            await model.aask("x", Triage)
        assert len(recorder.requests) == 1

    async def test_more_than_128_images_rejected_before_sending(self):
        image = {"type": "input_image", "image_url": "data:image/png;base64,AAAA"}
        messages = [{"role": "user", "content": [image] * 129}]
        model, recorder = _model()
        with pytest.raises(DecisionProviderRequestError, match="128"):
            await model.aask(messages, Triage)
        assert recorder.requests == []

    async def test_typesafe_schema_rejected(self):
        class Other(TypeSafeSchema):
            q = TypeSafeSchema.Noul(instructions="x")

        model, recorder = _model()
        with pytest.raises(DecisionProviderRequestError, match="OpenAISchema"):
            await model.aask("x", Other)
        assert recorder.requests == []
