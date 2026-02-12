import os
from unittest.mock import patch, MagicMock
import pytest
import litellm
from railtracks.llm.models.cloud import PortKeyLLM  # adjust path if needed
from railtracks.llm.providers import ModelProvider


MODEL_NAME = "portkey/deepseek-r1"


def test_model_distributor():
    """Test that the model distributor is correctly returned"""
    assert PortKeyLLM.model_gateway() == ModelProvider.PORTKEY


def test_model_type():
    """Test that the model type method returns ModelProvider.PORTKEY"""
    llm = PortKeyLLM(model_name=MODEL_NAME, api_key="test_api_key")
    assert llm.model_provider() == ModelProvider.PORTKEY





def test_init_success_with_env_api_key():
    """Test successful initialization when api_key is taken from environment"""
    example_key = "hello world"
   
    with patch.dict(os.environ, {"PORTKEY_API_KEY": example_key}, clear=True):

        llm = PortKeyLLM(model_name=MODEL_NAME)

        assert llm.api_key == example_key



def test_init_missing_api_key():
    """Test KeyError is raised when no API key is provided and env var is missing"""

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(KeyError, match="Please set your PORTKEY_API_KEY"):
            PortKeyLLM(model_name=MODEL_NAME)


def test_temperature_passed_to_litellm_completion(message_history):
    """Assert that when PortKeyLLM is created with temperature, it is passed to litellm.completion."""
    mock_portkey = MagicMock()
    mock_portkey.base_url = "https://api.portkey.ai"
    mock_portkey.api_key = "test_key"
    with patch("portkey_ai.Portkey", return_value=mock_portkey):
        with patch.object(litellm, "completion") as mock_completion:
            mock_completion.return_value = litellm.utils.ModelResponse(
                choices=[{"message": {"content": "ok"}}]
            )
            llm = PortKeyLLM(model_name=MODEL_NAME, api_key="test_key", temperature=0.6)
            llm.chat(message_history)
            mock_completion.assert_called_once()
            assert mock_completion.call_args.kwargs.get("temperature") == 0.6

