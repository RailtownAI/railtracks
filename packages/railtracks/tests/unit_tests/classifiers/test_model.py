"""TypeSafeAI.aask: HTTP request, error mapping, retries and the response."""

import httpx
import pytest
from railtracks.classifiers import (
    ClassifierAuthenticationError,
    ClassifierConnectionError,
    ClassifierError,
    ClassifierRateLimitError,
    ClassifierRequestError,
    ClassifierResponseError,
    ClassifierServerError,
    ClassifierTimeoutError,
    DecisionResponse,
    SchemaDefinitionError,
    TypeSafeAI,
)
from railtracks.exceptions._base import RTError
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
        with pytest.raises(ClassifierAuthenticationError, match="TYPESAFE_API_KEY"):
            await model.aask("Help!", Triage)
        assert recorder.requests == []

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
        assert resp.requested_model_name == "jev-latest"
        assert (
            resp.provider == "typesafe"
        )  # the host reports none; the class name fills in
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
        assert resp.requested_model_name == "jev-latest"
        assert resp.cost is None

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
            (401, ClassifierAuthenticationError),
            (403, ClassifierAuthenticationError),
            (429, ClassifierRateLimitError),
            (500, ClassifierServerError),
            (503, ClassifierServerError),
            (529, ClassifierServerError),
            (400, ClassifierRequestError),
            (404, ClassifierRequestError),
            (422, ClassifierRequestError),
        ],
    )
    async def test_status_maps_to_error(self, make_model, status, error):
        model, _ = make_model(httpx.Response(status, text="nope"))
        with pytest.raises(error, match=str(status)):
            await model.aask("Help!", Triage)

    async def test_request_error_carries_truncated_body(self, make_model):
        detail = '{"detail": [{"loc": ["body", "state"], "msg": "Field required"}]}'
        model, _ = make_model(httpx.Response(422, text=detail + "x" * 5000))
        with pytest.raises(ClassifierRequestError) as info:
            await model.aask("Help!", Triage)
        assert "Field required" in info.value.reason
        assert len(info.value.body) < 1000

    @pytest.mark.parametrize(
        "exc, error",
        [
            (httpx.ReadTimeout("slow"), ClassifierTimeoutError),
            (httpx.ConnectTimeout("slow"), ClassifierTimeoutError),
            (httpx.PoolTimeout("slow"), ClassifierTimeoutError),
            (httpx.ConnectError("refused"), ClassifierConnectionError),
            (httpx.RemoteProtocolError("dropped"), ClassifierConnectionError),
        ],
    )
    async def test_transport_errors_split_by_kind(self, make_model, exc, error):
        model, _ = make_model(exc)
        with pytest.raises(error) as info:
            await model.aask("Help!", Triage)
        assert info.value.__cause__ is exc

    @pytest.mark.parametrize(
        "exc",
        [httpx.InvalidURL("bad url"), httpx.UnsupportedProtocol("ftp://x")],
    )
    async def test_config_mistakes_are_request_errors(self, make_model, exc):
        model, _ = make_model(exc)
        with pytest.raises(ClassifierRequestError, match="api_base"):
            await model.aask("Help!", Triage)

    async def test_non_json_body(self, make_model):
        model, _ = make_model(httpx.Response(200, text="<html>"))
        with pytest.raises(ClassifierResponseError, match="JSON"):
            await model.aask("Help!", Triage)

    def test_family(self):
        for error in (
            ClassifierAuthenticationError,
            ClassifierConnectionError,
            ClassifierRateLimitError,
            ClassifierRequestError,
            ClassifierResponseError,
            ClassifierServerError,
            ClassifierTimeoutError,
        ):
            assert issubclass(error, ClassifierError)
        for root in (ClassifierError, SchemaDefinitionError):
            assert not issubclass(root, RTError)
        assert not issubclass(SchemaDefinitionError, ClassifierError)


class TestRetries:
    @pytest.mark.parametrize(
        "failure",
        [
            httpx.Response(429, text="slow down"),
            httpx.Response(503, text="overloaded"),
            httpx.ReadTimeout("slow"),
            httpx.ConnectError("refused"),
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
        with pytest.raises(ClassifierServerError) as info:
            await model.aask("Help!", Triage)
        assert len(recorder.requests) == 3
        assert any("3 attempts" in note for note in info.value.notes)

    async def test_exhausted_retries_keep_the_httpx_root_cause(self, make_model):
        root = httpx.ReadTimeout("slow")
        model, _ = make_model(root, retry_approach=FixedRetry(max_tries=2, delay=0.0))
        with pytest.raises(ClassifierTimeoutError) as info:
            await model.aask("Help!", Triage)

        chain, seen = [], set()
        error: BaseException | None = info.value
        while error is not None:
            assert id(error) not in seen, f"__cause__ cycle at {error!r}"
            seen.add(id(error))
            chain.append(error)
            error = error.__cause__
        assert chain[-1] is root
        assert [type(e) for e in chain] == [ClassifierTimeoutError, httpx.ReadTimeout]

    async def test_config_mistakes_not_retried(self, make_model):
        model, recorder = make_model(
            httpx.UnsupportedProtocol("ftp://x"),
            retry_approach=FixedRetry(max_tries=3, delay=0.0),
        )
        with pytest.raises(ClassifierRequestError):
            await model.aask("Help!", Triage)
        assert len(recorder.requests) == 1

    @pytest.mark.parametrize("status", [400, 401, 422])
    async def test_client_errors_not_retried(self, make_model, status):
        model, recorder = make_model(
            httpx.Response(status, text="no"),
            ok(),
            retry_approach=FixedRetry(max_tries=3, delay=0.0),
        )
        with pytest.raises(ClassifierError):
            await model.aask("Help!", Triage)
        assert len(recorder.requests) == 1

    async def test_no_retries_by_default(self, make_model):
        model, recorder = make_model(httpx.Response(429, text="slow down"), ok())
        with pytest.raises(ClassifierRateLimitError):
            await model.aask("Help!", Triage)
        assert len(recorder.requests) == 1
