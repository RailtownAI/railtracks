"""TypeSafeAI.aask: HTTP request, error mapping, retries and the response."""

import httpx
import pytest
from railtracks.built_nodes.decisions import DecisionResponse
from railtracks.built_nodes.decisions.typesafe import TypeSafeAI
from railtracks.exceptions import (
    DecisionAuthenticationError,
    DecisionModelError,
    DecisionRateLimitError,
    DecisionRequestError,
    DecisionResponseError,
    DecisionServerError,
    DecisionTimeoutError,
    NodeInvocationError,
)
from railtracks.llm.retries import FixedRetry

from .conftest import Triage, ok


class TestRequest:
    async def test_posts_systemone_with_bearer_key(self, make_model):
        model, recorder = make_model()
        await model.aask("Help!", Triage)

        request = recorder.requests[0]
        assert request.method == "POST"
        assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = recorder.body()
        assert body["model"] == "jev-latest"
        assert body["state"] == "Help!"
        assert list(body["questions"]) == ["is_urgent", "department", "frustration"]

    async def test_custom_api_base(self, make_model):
        model, recorder = make_model(api_base="https://openrouter.ai/api/")
        await model.aask("Help!", Triage)
        assert str(recorder.requests[0].url) == "https://openrouter.ai/api/v1/systemone"

    async def test_json_state(self, make_model):
        model, recorder = make_model()
        await model.aask({"subject": "Duplicate charge"}, Triage)
        assert recorder.body()["state"] == {"subject": "Duplicate charge"}

    async def test_api_key_falls_back_to_env(self, make_model, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "env-key")
        model, recorder = make_model(api_key=None)
        await model.aask("Help!", Triage)
        assert recorder.requests[0].headers["Authorization"] == "Bearer env-key"

    async def test_missing_api_key_raises_at_call_time(self, make_model, monkeypatch):
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        model, recorder = make_model(api_key=None)  # construction does not raise
        with pytest.raises(DecisionAuthenticationError, match="TYPESAFE_API_KEY"):
            await model.aask("Help!", Triage)
        assert recorder.requests == []

    async def test_provider_picks_the_api_key_env(self, make_model, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "typesafe-key")
        monkeypatch.setenv("LAYA_API_KEY", "laya-key")
        model, recorder = make_model(
            model_name="english",
            provider="laya",
            api_base="http://laya-server:8000",
            api_key=None,
        )
        await model.aask("Help!", Triage)
        assert recorder.requests[0].headers["Authorization"] == "Bearer laya-key"

    async def test_provider_env_name_is_normalised(self, make_model, monkeypatch):
        monkeypatch.setenv("MY_HOST_API_KEY", "host-key")
        model, recorder = make_model(
            provider="my-host", api_base="http://localhost:8008", api_key=None
        )
        await model.aask("Help!", Triage)
        assert recorder.requests[0].headers["Authorization"] == "Bearer host-key"

    async def test_self_hosted_server_without_a_key_gets_no_auth_header(
        self, make_model, monkeypatch
    ):
        monkeypatch.delenv("LAYA_API_KEY", raising=False)
        model, recorder = make_model(
            model_name="english",
            provider="laya",
            api_base="http://laya-server:8000",
            api_key=None,
        )
        await model.aask("Help!", Triage)
        assert "Authorization" not in recorder.requests[0].headers

    async def test_self_hosted_server_that_needs_a_key_reports_auth_error(
        self, make_model, monkeypatch
    ):
        monkeypatch.delenv("LAYA_API_KEY", raising=False)
        model, _ = make_model(
            httpx.Response(401, text="unauthorized"),
            provider="laya",
            api_base="http://laya-server:8000",
            api_key=None,
        )
        with pytest.raises(DecisionAuthenticationError, match="LAYA_API_KEY"):
            await model.aask("Help!", Triage)

    def test_construction_without_key_or_network(self, monkeypatch):
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        model = TypeSafeAI(model_name="jev-latest")
        assert model.model_name == "jev-latest"
        assert model.api_base == "https://api.typesafe.ai"


class TestResponse:
    async def test_returns_decision_response(self, make_model):
        model, _ = make_model()
        resp = await model.aask("Help!", Triage)

        assert isinstance(resp, DecisionResponse)
        assert isinstance(resp.structured, Triage)
        assert resp.structured.department.choice == "technical"
        assert resp.model_name == "jev-1.13.0"
        assert resp.provider is None
        assert resp.input_tokens == 296
        assert resp.output_tokens == 20
        assert resp.latency > 0
        assert resp.cost == pytest.approx(296 * 4.2e-08)
        assert resp.raw["usage"] == {"input_tokens": 296, "output_tokens": 20}

    async def test_model_name_falls_back_to_requested(self, make_model):
        body = {"answers": ok().json()["answers"]}
        model, _ = make_model(ok(body))
        resp = await model.aask("Help!", Triage)
        assert resp.model_name == "jev-latest"
        assert resp.cost is None

    async def test_provider_prefix_prices_free_self_hosted_models(self, make_model):
        # litellm lists laya/<checkpoint> at zero; known-free, not unknown
        model, _ = make_model(
            model_name="english", provider="laya", api_base="http://laya-server:8000"
        )
        resp = await model.aask("Help!", Triage)
        assert resp.cost == 0.0

    def test_pricing_keys_try_the_provider_prefix_first(self):
        model = TypeSafeAI("upstage/solar-decide", provider="openrouter")
        assert model._pricing_keys() == [
            "openrouter/upstage/solar-decide",
            "upstage/solar-decide",
        ]
        assert TypeSafeAI("jev-latest")._pricing_keys() == [
            "typesafe/jev-latest",
            "jev-latest",
            "openrouter/jev-latest",
        ]

    async def test_reported_cost_preferred_over_catalog(self, make_model):
        body = ok().json()
        body["usage"]["cost"] = 0.002
        model, _ = make_model(ok(body))
        resp = await model.aask("Help!", Triage)
        assert resp.cost == 0.002

    async def test_reported_cost_prices_models_missing_from_catalog(self, make_model):
        body = ok().json()
        body["usage"]["cost"] = 3e-05
        model, _ = make_model(ok(body), model_name="upstage/solar-decide")
        resp = await model.aask("Help!", Triage)
        assert resp.cost == 3e-05

    async def test_unpriced_model_has_no_cost(self, make_model):
        model, _ = make_model()
        model.model_name = "jaredpalmer/kev-4b"
        resp = await model.aask("Help!", Triage)
        assert resp.cost is None


class TestErrorMapping:
    @pytest.mark.parametrize(
        "status, error",
        [
            (401, DecisionAuthenticationError),
            (403, DecisionAuthenticationError),
            (429, DecisionRateLimitError),
            (500, DecisionServerError),
            (503, DecisionServerError),
            (529, DecisionServerError),
            (400, DecisionRequestError),
            (404, DecisionRequestError),
            (422, DecisionRequestError),
        ],
    )
    async def test_status_maps_to_error(self, make_model, status, error):
        model, _ = make_model(httpx.Response(status, text="nope"))
        with pytest.raises(error, match=str(status)):
            await model.aask("Help!", Triage)

    async def test_request_error_carries_truncated_body(self, make_model):
        detail = '{"detail": [{"loc": ["body", "state"], "msg": "Field required"}]}'
        model, _ = make_model(httpx.Response(422, text=detail + "x" * 5000))
        with pytest.raises(DecisionRequestError) as info:
            await model.aask("Help!", Triage)
        assert "Field required" in info.value.reason
        assert len(info.value.body) < 1000

    @pytest.mark.parametrize(
        "exc",
        [
            httpx.ReadTimeout("slow"),
            httpx.ConnectTimeout("slow"),
            httpx.ConnectError("refused"),
        ],
    )
    async def test_timeouts_and_connection_errors(self, make_model, exc):
        model, _ = make_model(exc)
        with pytest.raises(DecisionTimeoutError):
            await model.aask("Help!", Triage)

    async def test_non_json_body(self, make_model):
        model, _ = make_model(httpx.Response(200, text="<html>"))
        with pytest.raises(DecisionResponseError, match="JSON"):
            await model.aask("Help!", Triage)

    def test_family(self):
        for error in (
            DecisionAuthenticationError,
            DecisionRateLimitError,
            DecisionRequestError,
            DecisionResponseError,
            DecisionServerError,
            DecisionTimeoutError,
        ):
            assert issubclass(error, DecisionModelError)
        assert issubclass(DecisionModelError, NodeInvocationError)


class TestRetries:
    @pytest.mark.parametrize(
        "failure",
        [
            httpx.Response(429, text="slow down"),
            httpx.Response(503, text="overloaded"),
            httpx.ReadTimeout("slow"),
        ],
    )
    async def test_transient_errors_retried(self, make_model, failure):
        model, recorder = make_model(
            failure, ok(), retry_approach=FixedRetry(max_tries=3, delay=0.0)
        )
        resp = await model.aask("Help!", Triage)
        assert resp.structured.is_urgent.noul == 0.93
        assert len(recorder.requests) == 2

    async def test_exhausted_retries_raise_the_last_error(self, make_model):
        model, recorder = make_model(
            httpx.Response(500, text="boom"),
            retry_approach=FixedRetry(max_tries=3, delay=0.0),
        )
        with pytest.raises(DecisionServerError):
            await model.aask("Help!", Triage)
        assert len(recorder.requests) == 3

    @pytest.mark.parametrize("status", [400, 401, 422])
    async def test_client_errors_not_retried(self, make_model, status):
        model, recorder = make_model(
            httpx.Response(status, text="no"),
            ok(),
            retry_approach=FixedRetry(max_tries=3, delay=0.0),
        )
        with pytest.raises(DecisionModelError):
            await model.aask("Help!", Triage)
        assert len(recorder.requests) == 1

    async def test_no_retries_by_default(self, make_model):
        model, recorder = make_model(httpx.Response(429, text="slow down"), ok())
        with pytest.raises(DecisionRateLimitError):
            await model.aask("Help!", Triage)
        assert len(recorder.requests) == 1
