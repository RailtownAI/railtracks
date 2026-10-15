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
    OpenRouterDecisions,
    TypeSafeDecisions,
)

from .conftest import TRIAGE_BODY, Triage, respond

PROVIDERS = [TypeSafeDecisions, OpenRouterDecisions, OpenAIDecisions]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_providers_subclass_decision_model(provider):
    assert provider.__bases__ == (DecisionModel,)


def test_decision_model_is_the_one_concrete_base():
    assert not inspect.isabstract(DecisionModel)
    assert importlib.util.find_spec("railtracks.decisions.transport._litellm") is None
    assert importlib.util.find_spec("railtracks.decisions.pricing") is None
    for leftover in (
        "api_base",
        "_send",
        "describe_questions",
        "_key_notes",
        "_pricing_keys",
        "pricing_prefixes",
        "bills_output_tokens",
    ):
        assert not hasattr(DecisionModel, leftover)


def test_exports():
    assert rt.decisions.TypeSafeDecisions is TypeSafeDecisions
    assert rt.decisions.OpenRouterDecisions is OpenRouterDecisions
    assert rt.decisions.OpenAIDecisions is OpenAIDecisions
    for removed in (
        "TypeSafeSchema",
        "OpenAISchema",
        "NoulAnswer",
        "Noul",
        "TypeSafeAI",
        "OpenRouterAI",
        "TypeSafeCompatibleAI",
        "UpstageAI",
        "LayaAI",
        "LiteLLMProxyAI",
    ):
        assert not hasattr(rt.decisions, removed)


@pytest.mark.parametrize(
    "provider, model_name, litellm_model",
    [
        (TypeSafeDecisions, "jev-latest", "typesafe/jev-latest"),
        (OpenRouterDecisions, "typesafe/jev-1.13", "openrouter/typesafe/jev-1.13"),
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


class TestTypeSafeDecisions:
    def test_defaults(self):
        model = TypeSafeDecisions("jev-latest")
        assert model.provider_name == "typesafe"


# ================= OpenRouter =================


class TestOpenRouterDecisions:
    def test_defaults(self):
        assert OpenRouterDecisions("typesafe/jev-1.13").provider_name == "openrouter"

    async def test_cost_is_litellms_response_cost(self, make_model):
        model, _ = make_model(
            respond(cost=0.002), cls=OpenRouterDecisions, model_name="typesafe/jev-1.13"
        )
        resp = await model.aask("Help!", Triage)
        assert resp.cost == 0.002


# ================= OpenAI =================


class TestOpenAIDecisions:
    def test_defaults(self):
        assert OpenAIDecisions("gpt-6-luna").provider_name == "openai"

    @pytest.fixture
    def chat_priced_luna(self, monkeypatch):
        # litellm lists gpt-6-luna at chat prices; Decisions bills no output tokens
        monkeypatch.setitem(
            litellm.model_cost,
            "gpt-6-luna",
            {"input_cost_per_token": 1e-07, "output_cost_per_token": 5e-07},
        )

    async def test_cost_is_input_tokens_only(self, make_model, chat_priced_luna):
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

    async def test_unlisted_model_has_no_cost(self, make_model, monkeypatch):
        monkeypatch.delitem(litellm.model_cost, "gpt-unlisted", raising=False)
        model, _ = make_model(cls=OpenAIDecisions, model_name="gpt-unlisted")
        resp = await model.aask("x", Triage)
        assert resp.cost is None

    def test_no_input_tokens_means_no_cost(self, chat_priced_luna):
        # litellm's response type requires usage, so ask the cost hook directly
        assert OpenAIDecisions("gpt-6-luna")._cost(respond(), None) is None

    async def test_pricing_never_raises(self, make_model, monkeypatch):
        def boom(**kwargs):
            raise ValueError("bad catalog entry")

        monkeypatch.setattr(litellm, "cost_per_token", boom)
        model, _ = make_model(cls=OpenAIDecisions, model_name="gpt-6-luna")
        resp = await model.aask("x", Triage)
        assert resp.cost is None

    async def test_json_array_sent_as_json_text(self, make_model):
        state = [{"role": "user", "content": "Is this urgent?"}]
        model, fake = make_model(cls=OpenAIDecisions, model_name="gpt-6-luna")
        await model.aask(state, Triage)
        assert fake.last["input"] == json.dumps(state)
