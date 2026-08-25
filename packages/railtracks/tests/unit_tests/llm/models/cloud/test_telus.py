import os
from unittest.mock import patch

import litellm
import pytest
from railtracks.llm.models.cloud import TelusLLM
from railtracks.llm.providers import ModelProvider

MODEL_NAME = "telus/llama-3-70b"
API_BASE = "https://telus.example.com/v1"


def test_model_gateway():
    assert TelusLLM.model_gateway() == ModelProvider.TELUS


def test_init_success_with_env_api_key():
    with patch.dict(os.environ, {"TELUS_API_KEY": "hello world"}, clear=True):
        llm = TelusLLM(model_name=MODEL_NAME, api_base=API_BASE)
        assert llm.api_key == "hello world"


def test_init_missing_api_key():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(
            KeyError, match="Please set the TELUS_API_KEY environment variable"
        ):
            TelusLLM(model_name=MODEL_NAME, api_base=API_BASE)


def test_model_name_has_no_fake_openai_prefix():
    """TelusLLM must report the model name the caller configured - not a fake
    'openai/' prefix baked in for litellm's routing (see #1437)."""
    llm = TelusLLM(model_name=MODEL_NAME, api_base=API_BASE, api_key="test_key")
    assert llm.model_name() == MODEL_NAME


def test_custom_llm_provider_passed_to_litellm_completion(message_history):
    """The 'openai' routing hint litellm needs for gateway calls must be sent as
    a completion kwarg, not baked into the model name string (see #1437)."""
    with patch.object(litellm, "completion") as mock_completion:
        mock_completion.return_value = litellm.utils.ModelResponse(
            choices=[{"message": {"content": "ok"}}]
        )
        llm = TelusLLM(model_name=MODEL_NAME, api_base=API_BASE, api_key="test_key")
        llm.chat(message_history)
        mock_completion.assert_called_once()
        assert mock_completion.call_args.kwargs.get("model") == MODEL_NAME
        assert mock_completion.call_args.kwargs.get("custom_llm_provider") == "openai"


def test_temperature_passed_to_litellm_completion(message_history):
    with patch.object(litellm, "completion") as mock_completion:
        mock_completion.return_value = litellm.utils.ModelResponse(
            choices=[{"message": {"content": "ok"}}]
        )
        llm = TelusLLM(
            model_name=MODEL_NAME, api_base=API_BASE, api_key="test_key", temperature=0.6
        )
        llm.chat(message_history)
        mock_completion.assert_called_once()
        assert mock_completion.call_args.kwargs.get("temperature") == 0.6
