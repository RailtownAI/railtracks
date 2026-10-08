"""LiteLLMDecisionModel.aask: the litellm.adecisions call, error mapping, retries and
the response."""

import copy

import httpx
import litellm
import pytest
from railtracks.decisions import (
    DecisionProviderAuthenticationError,
    DecisionProviderConnectionError,
    DecisionProviderError,
    DecisionProviderRateLimitError,
    DecisionProviderRefusalError,
    DecisionProviderRequestError,
    DecisionProviderResponseError,
    DecisionProviderServerError,
    DecisionProviderTimeoutError,
    DecisionResponse,
    SchemaDefinitionError,
    TypeSafeAI,
)
from railtracks.exceptions._base import RTError
from railtracks.llm.retries import FixedRetry

from .conftest import TRIAGE_BODY, TRIAGE_COST, Triage, respond

_MODEL = "typesafe/jev-latest"
_PROVIDER = "typesafe"
_RESPONSE = httpx.Response(
    403, request=httpx.Request("POST", "https://api.typesafe.ai/v1/systemone")
)


def _bad_request(message: str = "Invalid Decisions request: too_short"):
    return litellm.BadRequestError(
        message=message,
        model=_MODEL,
        llm_provider=_PROVIDER,
    )


def _timeout():
    return litellm.Timeout(
        message="Connection timed out.",
        model="default-model-name",
        llm_provider="litellm-httpx-handler",
    )


def _connection():
    return litellm.APIConnectionError(
        message="TypesafeException - Cannot connect to host",
        llm_provider=_PROVIDER,
        model=_MODEL,
    )


def _rate_limit():
    return litellm.RateLimitError(
        message="slow down", llm_provider=_PROVIDER, model=_MODEL
    )


def _server():
    return litellm.InternalServerError(
        message="boom", llm_provider=_PROVIDER, model=_MODEL
    )


def _auth(message: str = 'TypesafeException - {"error": "invalid key"}'):
    return litellm.AuthenticationError(
        message=message, llm_provider=_PROVIDER, model=_MODEL
    )


class TestRequest:
    async def test_calls_adecisions_in_the_openai_shape(self, make_model):
        model, fake = make_model()
        await model.aask("Help!", Triage)

        [call] = fake.calls
        assert call["model"] == "typesafe/jev-latest"
        assert call["input"] == "Help!"
        assert [q["name"] for q in call["questions"]] == [
            "is_urgent",
            "department",
            "frustration",
        ]
        assert call["questions"][0] == {
            "type": "predicate",
            "name": "is_urgent",
            "instructions": "The message conveys urgency",
        }
        assert call["api_key"] == "test-key"
        assert call["api_base"] is None
        assert call["timeout"] == 30.0
        assert "state" not in call  # the System One shape drops refusals

    async def test_json_state_sent_as_json_text(self, make_model):
        model, fake = make_model()
        await model.aask({"subject": "Duplicate charge"}, Triage)
        assert fake.last["input"] == '{"subject": "Duplicate charge"}'

    async def test_api_base_and_timeout_passed_through(self, make_model):
        model, fake = make_model(api_base="https://proxy.example.com/v1", timeout=5.0)
        await model.aask("Help!", Triage)
        assert fake.last["api_base"] == "https://proxy.example.com/v1"
        assert fake.last["timeout"] == 5.0

    async def test_without_api_key_litellm_reads_the_env(self, make_model):
        model, fake = make_model(api_key=None)
        await model.aask("Help!", Triage)
        assert fake.last["api_key"] is None

    def test_construction_without_key_or_network(self):
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
        assert resp.provider == "typesafe"
        assert resp.input_tokens == 296
        assert resp.output_tokens == 20
        assert resp.latency > 0
        assert resp.cost == pytest.approx(TRIAGE_COST)
        assert resp.raw["usage"]["input_tokens"] == 296

    async def test_litellm_cost_preferred_over_catalog(self, make_model):
        model, _ = make_model(respond(cost=0.002))
        resp = await model.aask("Help!", Triage)
        assert resp.cost == 0.002

    async def test_catalog_price_without_litellm_cost(self, make_model):
        model, _ = make_model(respond(cost=None))
        resp = await model.aask("Help!", Triage)
        assert resp.cost == pytest.approx(296 * 4.2e-08)

    async def test_unpriced_model_has_no_cost(self, make_model):
        model, _ = make_model(respond(cost=None), model_name="kev-4b")
        resp = await model.aask("Help!", Triage)
        assert resp.cost is None

    @pytest.mark.parametrize(
        "cost", [-1.0, "0.1", True], ids=["negative", "str", "bool"]
    )
    async def test_unusable_litellm_cost_falls_back_to_catalog(self, make_model, cost):
        response = respond(cost=None)
        response._hidden_params["response_cost"] = cost
        model, _ = make_model(response)
        resp = await model.aask("Help!", Triage)
        assert resp.cost == pytest.approx(296 * 4.2e-08)

    async def test_refusal_raises(self, make_model):
        body = copy.deepcopy(TRIAGE_BODY)
        body["answers"][0] = {"type": "refusal", "name": "is_urgent"}
        model, _ = make_model(respond(body))
        with pytest.raises(DecisionProviderRefusalError) as info:
            await model.aask("Help!", Triage)
        assert info.value.refused == ["is_urgent"]


class TestErrorMapping:
    @pytest.mark.parametrize(
        "exc, error",
        [
            (_timeout(), DecisionProviderTimeoutError),
            (_rate_limit(), DecisionProviderRateLimitError),
            (_auth(), DecisionProviderAuthenticationError),
            (
                litellm.PermissionDeniedError(
                    message="forbidden",
                    llm_provider=_PROVIDER,
                    model=_MODEL,
                    response=_RESPONSE,
                ),
                DecisionProviderAuthenticationError,
            ),
            (_connection(), DecisionProviderConnectionError),
            (_server(), DecisionProviderServerError),
            (
                litellm.ServiceUnavailableError(
                    message="overloaded", llm_provider=_PROVIDER, model=_MODEL
                ),
                DecisionProviderServerError,
            ),
            (
                litellm.BadGatewayError(
                    message="bad gateway", llm_provider=_PROVIDER, model=_MODEL
                ),
                DecisionProviderServerError,
            ),
            (_bad_request(), DecisionProviderRequestError),
            (
                litellm.NotFoundError(
                    message="model_not_found", model=_MODEL, llm_provider=_PROVIDER
                ),
                DecisionProviderRequestError,
            ),
            (
                litellm.APIError(
                    status_code=502,
                    message="upstream",
                    llm_provider=_PROVIDER,
                    model=_MODEL,
                ),
                DecisionProviderServerError,
            ),
            (
                litellm.APIError(
                    status_code=409,
                    message="conflict",
                    llm_provider=_PROVIDER,
                    model=_MODEL,
                ),
                DecisionProviderRequestError,
            ),
            (
                litellm.APIResponseValidationError(
                    message="bad body", llm_provider=_PROVIDER, model=_MODEL
                ),
                DecisionProviderResponseError,
            ),
        ],
        ids=[
            "timeout",
            "rate-limit",
            "auth",
            "permission",
            "connection",
            "server",
            "unavailable",
            "bad-gateway",
            "bad-request",
            "not-found",
            "api-error-5xx",
            "api-error-4xx",
            "response-validation",
        ],
    )
    async def test_litellm_errors_map_to_provider_errors(self, make_model, exc, error):
        model, _ = make_model(exc)
        with pytest.raises(error) as info:
            await model.aask("Help!", Triage)
        assert type(info.value) is error
        assert info.value.__cause__ is exc

    async def test_timeout_checked_before_connection(self, make_model):
        # litellm.Timeout subclasses openai's APIConnectionError, not litellm's
        model, _ = make_model(_timeout())
        with pytest.raises(DecisionProviderTimeoutError):
            await model.aask("Help!", Triage)

    async def test_request_error_keeps_litellm_message_as_body(self, make_model):
        model, _ = make_model(_bad_request("Choice values must be unique" + "x" * 900))
        with pytest.raises(DecisionProviderRequestError) as info:
            await model.aask("Help!", Triage)
        assert "Choice values must be unique" in info.value.reason
        assert info.value.body.startswith(
            "litellm.BadRequestError: Choice values must be unique"
        )
        assert len(info.value.body) <= 500

    async def test_other_exceptions_propagate_unchanged(self, make_model):
        boom = RuntimeError("not a litellm error")
        model, _ = make_model(boom)
        with pytest.raises(RuntimeError) as info:
            await model.aask("Help!", Triage)
        assert info.value is boom

    def test_family(self):
        for error in (
            DecisionProviderAuthenticationError,
            DecisionProviderConnectionError,
            DecisionProviderRateLimitError,
            DecisionProviderRequestError,
            DecisionProviderResponseError,
            DecisionProviderServerError,
            DecisionProviderTimeoutError,
        ):
            assert issubclass(error, DecisionProviderError)
        for root in (DecisionProviderError, SchemaDefinitionError):
            assert not issubclass(root, RTError)
        assert not issubclass(SchemaDefinitionError, DecisionProviderError)


class TestKeyNotes:
    async def test_missing_key_names_the_env_var(self, make_model):
        missing = _auth("Missing API key for Decisions provider 'typesafe'")
        model, _ = make_model(missing, api_key=None)
        with pytest.raises(
            DecisionProviderAuthenticationError, match="TYPESAFE_API_KEY"
        ) as info:
            await model.aask("Help!", Triage)
        notes = " ".join(info.value.notes)
        assert "rejected" not in notes
        assert "Pass api_key= or set the TYPESAFE_API_KEY" in notes

    async def test_key_passed_as_argument_rejected(self, make_model):
        model, _ = make_model(_auth())
        with pytest.raises(DecisionProviderAuthenticationError) as info:
            await model.aask("Help!", Triage)
        notes = " ".join(info.value.notes)
        assert "rejected the key from the api_key= argument" in notes

    async def test_key_from_the_environment_rejected(self, make_model, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "env-key")
        model, _ = make_model(_auth(), api_key=None)
        with pytest.raises(DecisionProviderAuthenticationError) as info:
            await model.aask("Help!", Triage)
        notes = " ".join(info.value.notes)
        assert (
            "rejected the key from the TYPESAFE_API_KEY environment variable" in notes
        )


class TestRetries:
    @pytest.mark.parametrize(
        "failure",
        [_rate_limit(), _server(), _timeout(), _connection()],
        ids=["rate-limit", "server", "timeout", "connection"],
    )
    async def test_transient_errors_retried(self, make_model, failure):
        model, fake = make_model(
            failure, respond(), retry_approach=FixedRetry(max_tries=3, delay=0.0)
        )
        resp = await model.aask("Help!", Triage)
        assert resp.structured.is_urgent.probability == 0.93
        assert len(fake.calls) == 2

    async def test_exhausted_retries_raise_the_last_error(self, make_model):
        model, fake = make_model(
            _server(), retry_approach=FixedRetry(max_tries=3, delay=0.0)
        )
        with pytest.raises(DecisionProviderServerError) as info:
            await model.aask("Help!", Triage)
        assert len(fake.calls) == 3
        assert any("3 attempts" in note for note in info.value.notes)

    async def test_exhausted_retries_keep_the_litellm_root_cause(self, make_model):
        root = _timeout()
        model, _ = make_model(root, retry_approach=FixedRetry(max_tries=2, delay=0.0))
        with pytest.raises(DecisionProviderTimeoutError) as info:
            await model.aask("Help!", Triage)

        chain, seen = [], set()
        error: BaseException | None = info.value
        while error is not None:
            assert id(error) not in seen, f"__cause__ cycle at {error!r}"
            seen.add(id(error))
            chain.append(error)
            error = error.__cause__
        assert chain[-1] is root
        assert [type(e) for e in chain] == [
            DecisionProviderTimeoutError,
            litellm.Timeout,
        ]

    @pytest.mark.parametrize(
        "failure", [_bad_request(), _auth()], ids=["bad-request", "auth"]
    )
    async def test_client_errors_not_retried(self, make_model, failure):
        model, fake = make_model(
            failure, respond(), retry_approach=FixedRetry(max_tries=3, delay=0.0)
        )
        with pytest.raises(DecisionProviderError):
            await model.aask("Help!", Triage)
        assert len(fake.calls) == 1

    async def test_refusal_not_retried(self, make_model):
        body = copy.deepcopy(TRIAGE_BODY)
        body["answers"][0] = {"type": "refusal", "name": "is_urgent"}
        model, fake = make_model(
            respond(body), retry_approach=FixedRetry(max_tries=3, delay=0.0)
        )
        with pytest.raises(DecisionProviderRefusalError):
            await model.aask("Help!", Triage)
        assert len(fake.calls) == 1

    async def test_no_retries_by_default(self, make_model):
        model, fake = make_model(_rate_limit(), respond())
        with pytest.raises(DecisionProviderRateLimitError):
            await model.aask("Help!", Triage)
        assert len(fake.calls) == 1
