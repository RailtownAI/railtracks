import os
from unittest.mock import patch
import pytest
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
        
