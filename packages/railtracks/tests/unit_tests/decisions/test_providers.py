"""The three decision providers: litellm model prefix, api_base, keys, pricing and the
provider name."""

import copy

import litellm
import pytest
import railtracks as rt
from railtracks.decisions import (
    DecisionModel,
    DecisionProviderAuthenticationError,
    OpenAIDecisions,
    OpenRouterAI,
    TypeSafeAI,
)
from railtracks.decisions.transport._litellm import LiteLLMDecisionModel

from .conftest import TRIAGE_BODY, Triage, respond

PROVIDERS = [TypeSafeAI, OpenRouterAI, OpenAIDecisions]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_providers_share_the_litellm_base(provider):
    assert issubclass(provider, LiteLLMDecisionModel)
    assert issubclass(provider, DecisionModel)


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
        assert model.api_base == "https://api.typesafe.ai"

    def test_api_base_from_env_then_argument(self, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_BASE", "https://eu.typesafe.example")
        assert TypeSafeAI("jev-latest").api_base == "https://eu.typesafe.example"
        explicit = TypeSafeAI("jev-latest", api_base="https://mine.example")
        assert explicit.api_base == "https://mine.example"

    def test_pricing_keys_do_not_try_openrouter(self):
        assert TypeSafeAI("jev-latest")._pricing_keys() == [
            "typesafe/jev-latest",
            "jev-latest",
        ]


# ================= OpenRouter =================


class TestOpenRouterAI:
    def test_defaults(self, monkeypatch):
        model = OpenRouterAI("typesafe/jev-1.13")
        assert model.provider_name == "openrouter"
        assert model.api_base == "https://openrouter.ai/api"
        monkeypatch.setenv("OPENROUTER_API_BASE", "https://or.example/api")
        assert model.api_base == "https://or.example/api"

    async def test_missing_key_names_openrouter_env(self, make_model):
        missing = litellm.AuthenticationError(
            message="Missing API key for Decisions provider 'openrouter'",
            llm_provider="openrouter",
            model="openrouter/typesafe/jev-1.13",
        )
        model, _ = make_model(
            missing, cls=OpenRouterAI, model_name="typesafe/jev-1.13", api_key=None
        )
        with pytest.raises(
            DecisionProviderAuthenticationError, match="OPENROUTER_API_KEY"
        ):
            await model.aask("Help!", Triage)

    def test_pricing_keys(self):
        assert OpenRouterAI("typesafe/jev-1.13")._pricing_keys() == [
            "openrouter/typesafe/jev-1.13",
            "typesafe/jev-1.13",
        ]

    async def test_catalog_price(self, make_model):
        model, _ = make_model(
            respond(cost=None), cls=OpenRouterAI, model_name="typesafe/jev-1.13"
        )
        resp = await model.aask("Help!", Triage)
        assert resp.cost == pytest.approx(296 * 4.2e-08)


def _rejected(provider: str) -> litellm.AuthenticationError:
    return litellm.AuthenticationError(
        message="Incorrect API key provided", llm_provider=provider, model="m"
    )


# ================= OpenAI =================


class TestOpenAIDecisions:
    def test_defaults(self, monkeypatch):
        model = OpenAIDecisions("gpt-6-luna")
        assert model.provider_name == "openai"
        assert model.api_base == "https://api.openai.com/v1"
        monkeypatch.setenv("OPENAI_BASE_URL", "https://eu.api.openai.com/v1")
        assert model.api_base == "https://eu.api.openai.com/v1"

    def test_api_base_from_openai_api_base(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_BASE", "https://proxy.example.com/v1")
        assert OpenAIDecisions("gpt-6-luna").api_base == "https://proxy.example.com/v1"

    def test_api_base_precedence_matches_litellm(self, monkeypatch):
        model = OpenAIDecisions("gpt-6-luna")
        monkeypatch.setenv("OPENAI_API_BASE", "https://api-base.example.com/v1")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://base-url.example.com/v1")
        assert model.api_base == "https://base-url.example.com/v1"
        monkeypatch.setattr(litellm, "api_base", "https://global.example.com/v1")
        assert model.api_base == "https://global.example.com/v1"
        explicit = OpenAIDecisions("gpt-6-luna", api_base="https://own.example.com")
        assert explicit.api_base == "https://own.example.com"

    @pytest.mark.parametrize("provider", [TypeSafeAI, OpenRouterAI])
    def test_litellm_api_base_is_openai_only(self, monkeypatch, provider):
        monkeypatch.setattr(litellm, "api_base", "https://global.example.com/v1")
        assert provider("m").api_base == provider.default_api_base

    async def test_missing_key_names_openai_env(self, make_model):
        missing = litellm.AuthenticationError(
            message="Missing API key for Decisions provider 'openai'",
            llm_provider="openai",
            model="openai/gpt-6-luna",
        )
        model, _ = make_model(
            missing, cls=OpenAIDecisions, model_name="gpt-6-luna", api_key=None
        )
        with pytest.raises(DecisionProviderAuthenticationError, match="OPENAI_API_KEY"):
            await model.aask("Help!", Triage)

    @pytest.mark.parametrize("setting", ["api_key", "openai_key"])
    async def test_rejected_litellm_global_key_is_named(
        self, make_model, monkeypatch, setting
    ):
        # litellm's OpenAI path reads these globals before OPENAI_API_KEY
        monkeypatch.setattr(litellm, setting, "sk-global")
        model, _ = make_model(
            _rejected("openai"),
            cls=OpenAIDecisions,
            model_name="gpt-6-luna",
            api_key=None,
        )
        with pytest.raises(DecisionProviderAuthenticationError) as info:
            await model.aask("Help!", Triage)
        notes = " ".join(info.value.notes)
        assert f"rejected the key from litellm.{setting}" in notes

    @pytest.mark.parametrize("provider", [TypeSafeAI, OpenRouterAI])
    async def test_litellm_global_key_is_openai_only(
        self, make_model, monkeypatch, provider
    ):
        monkeypatch.setattr(litellm, "api_key", "sk-global")
        model, _ = make_model(_rejected("typesafe"), cls=provider, api_key=None)
        with pytest.raises(DecisionProviderAuthenticationError) as info:
            await model.aask("Help!", Triage)
        notes = " ".join(info.value.notes)
        assert "rejected" not in notes
        assert f"set the {provider.api_key_env} environment variable" in notes

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

    async def test_image_messages_passed_through(self, make_model):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Inspect this photo."},
                    {"type": "input_image", "image_url": "data:image/png;base64,AAAA"},
                ],
            }
        ]
        model, fake = make_model(cls=OpenAIDecisions, model_name="gpt-6-luna")
        await model.aask(messages, Triage)
        assert fake.last["input"] == messages
