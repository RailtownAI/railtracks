"""The /v1/systemone hosts: URL, keys, pricing keys, provider name and limits."""

import httpx
import pytest
from railtracks.decisions import (
    DecisionProviderAuthenticationError,
    DecisionProviderRequestError,
    DecisionProviderResponseError,
    LayaClassifier,
    LiteLLMProxyClassifier,
    OpenRouterClassifier,
    SystemOneProvider,
    TypeSafeAI,
    TypeSafeSchema,
)

from .conftest import TRIAGE_RESPONSE, Triage, ok

_HOST_ENV = (
    "TYPESAFE_API_KEY",
    "TYPESAFE_API_BASE",
    "OPENROUTER_API_KEY",
    "LAYA_API_KEY",
    "LAYA_API_BASE",
    "LITELLM_PROXY_API_KEY",
    "LITELLM_PROXY_API_BASE",
)


@pytest.fixture(autouse=True)
def _no_host_env(monkeypatch):
    for name in _HOST_ENV:
        monkeypatch.delenv(name, raising=False)


class Department(TypeSafeSchema):
    department = TypeSafeSchema.Choice(
        instructions="Choose the department that should help",
        criteria={"billing": "Invoices and refunds", "technical": "Bugs"},
    )


def _labels(count: int) -> type[TypeSafeSchema]:
    criteria = {f"label_{i}": f"option {i}" for i in range(count)}
    return type(
        "Wide",
        (TypeSafeSchema,),
        {"pick": TypeSafeSchema.Choice(instructions="Pick one", criteria=criteria)},
    )


def _questions(count: int) -> type[TypeSafeSchema]:
    return type(
        "Many",
        (TypeSafeSchema,),
        {
            f"q{i}": TypeSafeSchema.Noul(instructions=f"Question {i}")
            for i in range(count)
        },
    )


def _answer_department() -> httpx.Response:
    answers = {
        "department": {
            "type": "choice",
            "choice": "billing",
            "confidence": 0.9,
            "probabilities": {"billing": 0.97, "technical": 0.03},
        }
    }
    return ok({"model": "english", "answers": answers, "usage": {"input_tokens": 30}})


def test_hosts_share_the_systemone_base():
    for host in (
        TypeSafeAI,
        OpenRouterClassifier,
        LayaClassifier,
        LiteLLMProxyClassifier,
    ):
        assert issubclass(host, SystemOneProvider)
        assert host.schema_base is TypeSafeSchema


# ================= TypeSafe =================


class TestTypeSafeAI:
    async def test_defaults(self, make_model):
        model, recorder = make_model()
        resp = await model.aask("Help!", Triage)
        assert str(recorder.requests[0].url) == "https://api.typesafe.ai/v1/systemone"
        assert recorder.requests[0].headers["Authorization"] == "Bearer test-key"
        assert resp.provider == "typesafe"

    async def test_key_and_base_from_env(self, make_model, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "env-key")
        monkeypatch.setenv("TYPESAFE_API_BASE", "https://eu.typesafe.example/")
        model, recorder = make_model(api_key=None)
        await model.aask("Help!", Triage)
        assert (
            str(recorder.requests[0].url) == "https://eu.typesafe.example/v1/systemone"
        )
        assert recorder.requests[0].headers["Authorization"] == "Bearer env-key"

    async def test_requires_a_key(self, make_model):
        model, recorder = make_model(api_key=None)
        with pytest.raises(
            DecisionProviderAuthenticationError, match="TYPESAFE_API_KEY"
        ):
            await model.aask("Help!", Triage)
        assert recorder.requests == []

    def test_pricing_keys_do_not_try_openrouter(self):
        assert TypeSafeAI("jev-latest")._pricing_keys() == [
            "typesafe/jev-latest",
            "jev-latest",
        ]


# ================= OpenRouter =================


class TestOpenRouterClassifier:
    async def test_defaults_and_reported_provider(self, make_model):
        body = {**TRIAGE_RESPONSE, "provider": "TypeSafe"}
        model, recorder = make_model(
            ok(body), cls=OpenRouterClassifier, model_name="typesafe/jev-1.13"
        )
        resp = await model.aask("Help!", Triage)
        assert str(recorder.requests[0].url) == "https://openrouter.ai/api/v1/systemone"
        assert recorder.body()["model"] == "typesafe/jev-1.13"
        assert resp.provider == "TypeSafe"  # what OpenRouter reports wins

    async def test_requires_a_key_from_env(self, make_model, monkeypatch):
        model, recorder = make_model(cls=OpenRouterClassifier, api_key=None)
        with pytest.raises(
            DecisionProviderAuthenticationError, match="OPENROUTER_API_KEY"
        ):
            await model.aask("Help!", Triage)
        assert recorder.requests == []

        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        await model.aask("Help!", Triage)
        assert recorder.requests[0].headers["Authorization"] == "Bearer or-key"

    def test_pricing_keys(self):
        assert OpenRouterClassifier("typesafe/jev-1.13")._pricing_keys() == [
            "openrouter/typesafe/jev-1.13",
            "typesafe/jev-1.13",
        ]

    async def test_catalog_price(self, make_model):
        model, _ = make_model(cls=OpenRouterClassifier, model_name="typesafe/jev-1.13")
        resp = await model.aask("Help!", Triage)
        assert resp.cost == pytest.approx(296 * 4.2e-08)


# ================= Laya =================


class TestLayaClassifier:
    async def test_needs_a_base_url(self, make_model):
        model, recorder = make_model(cls=LayaClassifier, model_name="english")
        with pytest.raises(DecisionProviderRequestError, match="LAYA_API_BASE"):
            await model.aask("Help!", Department)
        assert recorder.requests == []

    async def test_base_from_env_and_no_key_needed(self, make_model, monkeypatch):
        monkeypatch.setenv("LAYA_API_BASE", "http://laya-server:8000")
        model, recorder = make_model(
            _answer_department(), cls=LayaClassifier, model_name="english", api_key=None
        )
        resp = await model.aask("Help!", Department)
        request = recorder.requests[0]
        assert str(request.url) == "http://laya-server:8000/v1/systemone"
        assert "Authorization" not in request.headers
        assert resp.provider == "laya"
        assert resp.cost == 0.0  # litellm lists laya/english at zero

    async def test_optional_key_from_env(self, make_model, monkeypatch):
        monkeypatch.setenv("LAYA_API_KEY", "laya-key")
        model, recorder = make_model(
            _answer_department(),
            cls=LayaClassifier,
            model_name="english",
            api_base="http://localhost:8000",
            api_key=None,
        )
        await model.aask("Help!", Department)
        assert recorder.requests[0].headers["Authorization"] == "Bearer laya-key"

    def test_pricing_keys(self):
        assert LayaClassifier("english")._pricing_keys() == ["laya/english", "english"]

    @pytest.mark.parametrize(
        "schema, state, limit",
        [
            (_labels(101), "Help!", "100 options"),
            (_questions(65), "Help!", "64 questions"),
            (Department, "x" * 50_001, "50000 characters"),
            (Department, {"text": "x" * 50_000}, "50000 characters"),
        ],
        ids=["choice-options", "questions", "text-state", "json-state"],
    )
    async def test_limits_checked_before_sending(
        self, make_model, schema, state, limit
    ):
        model, recorder = make_model(
            cls=LayaClassifier, model_name="english", api_base="http://localhost:8000"
        )
        with pytest.raises(DecisionProviderRequestError, match=limit):
            await model.aask(state, schema)
        assert recorder.requests == []

    async def test_at_the_limits_is_allowed(self, make_model):
        model, recorder = make_model(
            cls=LayaClassifier, model_name="english", api_base="http://localhost:8000"
        )
        # sent, then the canned Triage reply doesn't fit this schema
        with pytest.raises(DecisionProviderResponseError):
            await model.aask("x" * 50_000, _labels(100))
        assert len(recorder.requests) == 1


def test_typesafe_has_no_host_limits_beyond_the_format():
    assert TypeSafeAI.max_choice_labels is None
    assert TypeSafeAI.max_questions is None
    assert TypeSafeAI.max_state_chars is None


# ================= LiteLLM proxy =================


class TestLiteLLMProxyClassifier:
    @pytest.mark.parametrize("upstream", ["typesafe", "laya", "bespoke"])
    async def test_url_per_upstream(self, make_model, upstream):
        model, recorder = make_model(
            cls=LiteLLMProxyClassifier,
            upstream=upstream,
            api_base="http://localhost:4000/",
        )
        await model.aask("Help!", Triage)
        assert str(recorder.requests[0].url) == (
            f"http://localhost:4000/{upstream}/v1/systemone"
        )

    async def test_base_and_virtual_key_from_env(self, make_model, monkeypatch):
        monkeypatch.setenv("LITELLM_PROXY_API_BASE", "http://proxy:4000")
        monkeypatch.setenv("LITELLM_PROXY_API_KEY", "sk-virtual")
        model, recorder = make_model(
            cls=LiteLLMProxyClassifier, upstream="typesafe", api_key=None
        )
        await model.aask("Help!", Triage)
        assert (
            str(recorder.requests[0].url) == "http://proxy:4000/typesafe/v1/systemone"
        )
        assert recorder.requests[0].headers["Authorization"] == "Bearer sk-virtual"

    async def test_needs_a_base_url(self, make_model):
        model, recorder = make_model(cls=LiteLLMProxyClassifier, upstream="typesafe")
        with pytest.raises(
            DecisionProviderRequestError, match="LITELLM_PROXY_API_BASE"
        ):
            await model.aask("Help!", Triage)
        assert recorder.requests == []

    @pytest.mark.parametrize("status", [401, 403])
    async def test_rejected_key_names_the_virtual_key(self, make_model, status):
        model, _ = make_model(
            httpx.Response(status, text="key not allowed for model"),
            cls=LiteLLMProxyClassifier,
            upstream="laya",
            model_name="english",
            api_base="http://proxy:4000",
        )
        with pytest.raises(DecisionProviderAuthenticationError) as info:
            await model.aask("Help!", Department)
        notes = " ".join(info.value.notes)
        assert "LITELLM_PROXY_API_KEY" in notes
        assert "laya/english" in notes

    @pytest.mark.parametrize(
        "upstream, keys",
        [
            ("typesafe", ["typesafe/jev-latest", "jev-latest"]),
            ("laya", ["laya/jev-latest", "jev-latest"]),
        ],
    )
    def test_pricing_keys(self, upstream, keys):
        model = LiteLLMProxyClassifier("jev-latest", upstream=upstream)
        assert model._pricing_keys() == keys
        assert model.provider_name == upstream

    async def test_laya_upstream_has_laya_limits(self, make_model):
        model, recorder = make_model(
            cls=LiteLLMProxyClassifier,
            upstream="laya",
            model_name="english",
            api_base="http://proxy:4000",
        )
        with pytest.raises(DecisionProviderRequestError, match="100 options"):
            await model.aask("Help!", _labels(101))
        assert recorder.requests == []

    def test_unknown_upstream_rejected(self):
        with pytest.raises(ValueError, match="upstream"):
            LiteLLMProxyClassifier("jev-latest", upstream="openai")
