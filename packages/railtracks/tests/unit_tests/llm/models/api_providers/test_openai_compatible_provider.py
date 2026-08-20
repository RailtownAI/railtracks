from unittest.mock import patch

import litellm
from railtracks.llm.models.api_providers._openai_compatable_provider_wrapper import (
    OpenAICompatibleProvider,
)
from railtracks.llm.providers import ModelProvider

MODEL_NAME = "mistral-large-custom-deploy"
API_BASE = "https://gw.example.com/v1"


def test_model_gateway_is_unknown():
    assert OpenAICompatibleProvider.model_gateway() == ModelProvider.UNKNOWN


def test_full_model_name_is_identity():
    """The model name reported to callers/telemetry must be exactly what the user
    configured - OpenAICompatibleProvider must not inject a fake `openai/` prefix,
    since there's no real "openai" model behind these gateways (see #1437)."""
    llm = OpenAICompatibleProvider(MODEL_NAME, api_base=API_BASE, api_key="test-key")
    assert llm.model_name() == MODEL_NAME


def test_custom_llm_provider_passed_to_litellm_completion(message_history):
    """litellm's own routing (get_llm_provider) hard-fails on unrecognized model
    names without a provider hint. OpenAICompatibleProvider must supply that hint
    via the `custom_llm_provider` completion kwarg, not by mutating the model
    name string (see #1437)."""
    with patch.object(litellm, "completion") as mock_completion:
        mock_completion.return_value = litellm.utils.ModelResponse(
            choices=[{"message": {"content": "ok"}}]
        )
        llm = OpenAICompatibleProvider(MODEL_NAME, api_base=API_BASE, api_key="test-key")
        llm.chat(message_history)

        mock_completion.assert_called_once()
        assert mock_completion.call_args.kwargs.get("model") == MODEL_NAME
        assert mock_completion.call_args.kwargs.get("custom_llm_provider") == "openai"


def test_custom_llm_provider_cannot_be_overridden(message_history):
    """`custom_llm_provider` is the entire mechanism keeping litellm routing
    working for this class - a caller passing a different value must not be able
    to break it."""
    with patch.object(litellm, "completion") as mock_completion:
        mock_completion.return_value = litellm.utils.ModelResponse(
            choices=[{"message": {"content": "ok"}}]
        )
        llm = OpenAICompatibleProvider(
            MODEL_NAME,
            api_base=API_BASE,
            api_key="test-key",
            custom_llm_provider="anthropic",
        )
        llm.chat(message_history)

        assert mock_completion.call_args.kwargs.get("custom_llm_provider") == "openai"
