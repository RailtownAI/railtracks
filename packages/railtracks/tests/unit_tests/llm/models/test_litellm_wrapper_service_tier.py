"""Cost of a response priced at the service tier the provider reports it served (#1609).

litellm prices a buffered response at the tier the request asked for. A provider that serves a
different tier (a downgraded priority request, for example) bills that tier, so the reported
cost has to come from the served one.
"""

from unittest.mock import patch

import pytest
from litellm.types.utils import ModelResponse, Usage
from railtracks.llm.models._litellm_wrapper import LiteLLMWrapper


def _response(cost: float = 0.00123) -> ModelResponse:
    response = ModelResponse(
        model="gpt-4o",
        choices=[],
        usage=Usage(prompt_tokens=1000, completion_tokens=100, total_tokens=1100),
    )
    response._hidden_params["response_cost"] = cost
    return response


def test_a_served_tier_reprices_the_reported_cost() -> None:
    response = _response()
    response.service_tier = "default"

    with patch("litellm.completion_cost", return_value=0.0002) as completion_cost:
        info = LiteLLMWrapper.extract_message_info(
            response, 0.0, requested_model="gpt-4o"
        )

    completion_cost.assert_called_once()
    assert completion_cost.call_args.kwargs["service_tier"] == "default"
    assert info.total_cost == pytest.approx(0.0002)


def test_without_a_served_tier_the_reported_cost_stands() -> None:
    response = _response()

    with patch("litellm.completion_cost") as completion_cost:
        info = LiteLLMWrapper.extract_message_info(
            response, 0.0, requested_model="gpt-4o"
        )

    completion_cost.assert_not_called()
    assert info.total_cost == pytest.approx(0.00123)


def test_a_repricing_that_fails_keeps_the_reported_cost() -> None:
    response = _response()
    response.service_tier = "default"

    with patch(
        "litellm.completion_cost", side_effect=Exception("no price for the tier")
    ):
        info = LiteLLMWrapper.extract_message_info(
            response, 0.0, requested_model="gpt-4o"
        )

    assert info.total_cost == pytest.approx(0.00123)
