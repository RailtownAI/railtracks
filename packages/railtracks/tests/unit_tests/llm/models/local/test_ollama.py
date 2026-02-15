import os
import pytest
import requests
from typing import Generator
from unittest.mock import patch, MagicMock

import litellm
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper

from railtracks.llm.models.local.ollama import OllamaLLM
from railtracks.llm._exception_base import RTLLMError
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import UserMessage

@pytest.fixture
def mock_response():
    """Fixture for mocking successful API response"""
    mock = MagicMock()
    mock.json.return_value = {
        "models": [
            {"name": "test-model"},
            {"name": "llama2"}
        ]
    }
    mock.raise_for_status.return_value = None
    return mock


@pytest.fixture
def mock_failed_response():
    """Fixture for mocking failed API response"""
    mock = MagicMock()
    mock.raise_for_status.side_effect = requests.exceptions.RequestException("Connection failed")
    return mock


def test_model_type():
    """Test the model_type class method"""
    assert OllamaLLM.model_gateway() == "Ollama"
def test_init_success(mock_response):
    """Test successful initialization of Ollama"""
    with patch('requests.get', return_value=mock_response):
        ollama = OllamaLLM("test-model")
        assert ollama.model_name() == "ollama/test-model"
        assert ollama.domain == "http://localhost:11434"


def test_init_with_stream_enabled(mock_response):
    """Test initialization with streaming enabled"""
    with patch('requests.get', return_value=mock_response):
        ollama = OllamaLLM("test-model", stream=True)
        assert ollama.stream is True
        assert ollama.model_name() == "ollama/test-model"
        assert ollama.domain == "http://localhost:11434"


def test_init_with_stream_disabled(mock_response):
    """Test initialization with streaming disabled (default)"""
    with patch('requests.get', return_value=mock_response):
        ollama = OllamaLLM("test-model", stream=False)
        assert ollama.stream is False
        assert ollama.model_name() == "ollama/test-model"


def test_init_stream_defaults_to_false(mock_response):
    """Test that stream defaults to False when not specified"""
    with patch('requests.get', return_value=mock_response):
        ollama = OllamaLLM("test-model")
        assert ollama.stream is False


def test_chat_with_streaming(mock_response):
    """Test that chat method returns a generator when streaming is enabled"""
    with patch('requests.get', return_value=mock_response):
        ollama = OllamaLLM("test-model", stream=True)
        messages = MessageHistory([UserMessage(content="test message")])
        
        # Create a mock CustomStreamWrapper that can be iterated
        # The actual _stream_handler_base will process this and yield chunks
        mock_chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello", tool_calls=None), finish_reason="")]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" ", tool_calls=None), finish_reason="")]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="world", tool_calls=None), finish_reason="")]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=None, tool_calls=None), finish_reason="stop")]),
            MagicMock(choices=[]),
        ]
        
        def mock_stream_iter():
            for chunk in mock_chunks:
                yield chunk
        
        mock_stream_wrapper = MagicMock(spec=CustomStreamWrapper)
        mock_stream_wrapper.__iter__ = lambda self: mock_stream_iter()
        mock_stream_wrapper.model = "test-model"
        
        # Mock _invoke to return the stream wrapper
        with patch.object(ollama, '_invoke', return_value=(mock_stream_wrapper, 0.0)):
            result = ollama.chat(messages)
            
            # When streaming is enabled, chat should return a Generator
            assert isinstance(result, Generator)
            
            # Verify we can iterate through the generator
            chunks = list(result)
            # Should yield content chunks and a final Response
            assert len(chunks) > 0


def test_init_with_custom_domain(mock_response):
    """Test initialization with custom domain"""
    custom_domain = "http://custom-domain:11434"
    with patch('requests.get', return_value=mock_response):
        ollama = OllamaLLM("test-model", domain="custom", custom_domain=custom_domain)
        assert ollama.domain == custom_domain


def test_temperature_passed_to_litellm_completion(mock_response):
    """Assert that when OllamaLLM is created with temperature, it is passed to litellm.completion."""
    with patch('requests.get', return_value=mock_response):
        with patch.object(litellm, "completion") as mock_completion:
            mock_completion.return_value = litellm.utils.ModelResponse(
                choices=[{"message": {"content": "ok"}}]
            )
            ollama = OllamaLLM("test-model", temperature=0.7)
            messages = MessageHistory([UserMessage(content="test message")])
            ollama.chat(messages)
            mock_completion.assert_called_once()
            assert mock_completion.call_args.kwargs.get("temperature") == 0.7


def test_init_model_not_available(mock_response):
    """Test initialization with unavailable model"""
    with patch('requests.get', return_value=mock_response):
        with pytest.raises(RTLLMError) as exc_info:
            OllamaLLM("unavailable-model")
        assert "not available on server" in str(exc_info.value)


def test_init_connection_error(mock_failed_response):
    """Test initialization with connection error"""
    with patch('requests.get', return_value=mock_failed_response):
        with pytest.raises(requests.exceptions.RequestException):
            OllamaLLM("test-model")


def test_run_check_success(mock_response):
    """Test successful API check"""
    with patch('requests.get', return_value=mock_response):
        ollama = OllamaLLM("test-model")
        # Should not raise any exception
        ollama._run_check("api/tags")


def test_run_check_connection_error(mock_failed_response):
    """Test API check with connection error"""
    with patch('requests.get', side_effect=requests.exceptions.RequestException("Connection failed")):
        with pytest.raises(requests.exceptions.RequestException):
            OllamaLLM("test-model")


def test_chat_with_tools_unsupported(mock_response):
    """Test chat_with_tools with unsupported model"""
    with patch('requests.get', return_value=mock_response):
        with patch.object(litellm, 'supports_function_calling', return_value=False):
            ollama = OllamaLLM("test-model")
            messages = MessageHistory([UserMessage(content="test message")])
            tools = []

            with pytest.raises(RTLLMError) as exc_info:
                ollama.chat_with_tools(messages, tools)
            assert "does not support function calling" in str(exc_info.value)


def test_model_name_extraction(mock_response):
    """Test model name extraction from full path"""
    with patch('requests.get', return_value=mock_response):
        ollama = OllamaLLM("ollama/test-model")
        assert ollama.model_name() == "ollama/test-model"
        ollama2 = OllamaLLM("test-model")
        assert ollama2.model_name() == "ollama/test-model"


def test_init_with_auto_domain_missing_env(mock_response):
    """Test initialization with auto domain but missing environment variable"""
    with patch('requests.get', return_value=mock_response):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RTLLMError) as exc_info:
                OllamaLLM("test-model", domain="auto")
            assert "OLLAMA_HOST environment variable not set" in str(exc_info.value)


def test_init_with_custom_domain_missing_env(mock_response):
    """Test initialization with custom domain but missing environment variable"""
    with patch('requests.get', return_value=mock_response):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RTLLMError) as exc_info:
                OllamaLLM("test-model", domain="auto")
            assert "OLLAMA_HOST environment variable not set" in str(exc_info.value)


def test_init_with_default_domain(mock_response):
    """Test initialization with default domain setting"""
    with patch('requests.get', return_value=mock_response):
        ollama = OllamaLLM("test-model", domain="default")
        assert ollama.domain == "http://localhost:11434"


def test_init_with_auto_domain(mock_response):
    """Test initialization with auto domain"""
    custom_domain = "http://custom-domain:11434"
    with patch('requests.get', return_value=mock_response):
        with patch.dict(os.environ, {'OLLAMA_HOST': custom_domain}):
            ollama = OllamaLLM("test-model", domain="auto")
            assert ollama.domain == custom_domain


def test_init_with_custom_domain_missing_arg(mock_response):
    """Test initialization with custom domain but missing custom_domain argument"""
    with patch('requests.get', return_value=mock_response):
        with pytest.raises(RTLLMError) as exc_info:
            OllamaLLM("test-model", domain="custom")
        assert "Custom domain must be provided" in str(exc_info.value)
