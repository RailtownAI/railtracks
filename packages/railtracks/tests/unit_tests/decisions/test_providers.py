"""The three decision providers: litellm model prefix, pricing and the provider name."""

import copy
import importlib.util
import inspect
import json

import litellm
import pytest
import railtracks as rt
from railtracks.decisions import (
    DecisionModel,
    OpenAIDecisions,
    OpenRouterAI,
    TypeSafeAI,
)

from .conftest import TRIAGE_BODY, Triage, respond

PROVIDERS = [TypeSafeAI, OpenRouterAI, OpenAIDecisions]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_providers_subclass_decision_model(provider):
    assert provider.__bases__ == (DecisionModel,)


def test_decision_model_is_the_one_concrete_base():
    assert not inspect.isabstract(DecisionModel)
    assert importlib.util.find_spec("railtracks.decisions.transport._litellm") is None
    for leftover in ("api_base", "_send", "describe_questions", "_key_notes"):
        assert not hasattr(DecisionModel, leftover)


def test_exports():
    assert rt.decisions.TypeSafeAI is TypeSafeAI
    assert rt.decisions.OpenRouterAI is OpenRouterAI
    assert rt.decisions.OpenAIDecisions is OpenAIDecisions
    for removed in (
        "TypeSafeSchema",
        "OpenAISchema",
        "NoulAnswer",
        "TypeSafeCompatibleAI",
        "UpstageAI",
        "LayaAI",
        "LiteLLMProxyAI",
    ):
        assert not hasattr(rt.decisions, removed)


@pytest.mark.parametrize(
    "provider, model_name, litellm_model",
    [
        (TypeSafeAI, "jev-latest", "typesafe/jev-latest"),
        (OpenRouterAI, "typesafe/jev-1.13", "openrouter/typesafe/jev-1.13"),
        (OpenAIDecisions, "gpt-6-luna", "openai/gpt-6-luna"),
    ],
)
async def test_litellm_model_carries_the_provider_prefix(
    make_model, provider, model_name, litellm_model
):
    model, fake = make_model(cls=provider, model_name=model_name)
    resp = await model.aask("Help!", Triage)
    assert fake.last["model"] == litellm_model
    assert resp.requested_model_name == model_name
    assert resp.provider == provider.provider_name


# ================= TypeSafe =================


class TestTypeSafeAI:
    def test_defaults(self):
        model = TypeSafeAI("jev-latest")
        assert model.provider_name == "typesafe"

    def test_pricing_keys_do_not_try_openrouter(self):
        assert TypeSafeAI("jev-latest")._pricing_keys() == [
            "typesafe/jev-latest",
            "jev-latest",
        ]


# ================= OpenRouter =================


class TestOpenRouterAI:
    def test_defaults(self):
        assert OpenRouterAI("typesafe/jev-1.13").provider_name == "openrouter"

    def test_pricing_keys(self):
        assert OpenRouterAI("typesafe/jev-1.13")._pricing_keys() == [
            "openrouter/typesafe/jev-1.13",
            "typesafe/jev-1.13",
        ]

    async def test_catalog_price(self, make_model, monkeypatch):
        # litellm fetches its catalog at import; pin the entry so this stays offline
        monkeypatch.setitem(
            litellm.model_cost,
            "openrouter/typesafe/jev-1.13",
            {"input_cost_per_token": 4.2e-08, "output_cost_per_token": 0.0},
        )
        model, _ = make_model(
            respond(cost=None), cls=OpenRouterAI, model_name="typesafe/jev-1.13"
        )
        resp = await model.aask("Help!", Triage)
        assert resp.cost == pytest.approx(296 * 4.2e-08)


# ================= OpenAI =================


class TestOpenAIDecisions:
    def test_defaults(self):
        assert OpenAIDecisions("gpt-6-luna").provider_name == "openai"

    def test_pricing_keys(self):
        assert OpenAIDecisions("gpt-6-luna")._pricing_keys() == ["gpt-6-luna"]

    @pytest.fixture
    def chat_priced_luna(self, monkeypatch):
        # litellm lists gpt-6-luna at chat prices; Decisions bills no output tokens
        monkeypatch.setitem(
            litellm.model_cost,
            "gpt-6-luna",
            {"input_cost_per_token": 1e-07, "output_cost_per_token": 5e-07},
        )

    async def test_catalog_cost_is_input_tokens_only(
        self, make_model, chat_priced_luna
    ):
        model, _ = make_model(
            respond(cost=None), cls=OpenAIDecisions, model_name="gpt-6-luna"
        )
        resp = await model.aask("x", Triage)
        assert resp.cost == pytest.approx(296 * 1e-07)

    async def test_litellm_cost_used_when_no_output_tokens(
        self, make_model, chat_priced_luna
    ):
        body = copy.deepcopy(TRIAGE_BODY)
        body["usage"]["output_tokens"] = 0
        model, _ = make_model(
            respond(body, cost=296 * 1e-07),
            cls=OpenAIDecisions,
            model_name="gpt-6-luna",
        )
        resp = await model.aask("x", Triage)
        assert resp.cost == pytest.approx(296 * 1e-07)

    async def test_litellm_cost_billing_output_tokens_ignored(
        self, make_model, chat_priced_luna
    ):
        # litellm prices output at the chat rate; the Decisions API never bills it
        model, _ = make_model(
            respond(cost=296 * 1e-07 + 20 * 5e-07),
            cls=OpenAIDecisions,
            model_name="gpt-6-luna",
        )
        resp = await model.aask("x", Triage)
        assert resp.cost == pytest.approx(296 * 1e-07)

    async def test_json_array_sent_as_json_text(self, make_model):
        state = [{"role": "user", "content": "Is this urgent?"}]
        model, fake = make_model(cls=OpenAIDecisions, model_name="gpt-6-luna")
        await model.aask(state, Triage)
        assert fake.last["input"] == json.dumps(state)
