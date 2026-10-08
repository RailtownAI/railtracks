import base64
import os
from unittest.mock import MagicMock, patch

import litellm
import pytest
import requests
from railtracks.llm._exceptions import ProviderError
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage, UserMessage
from railtracks.llm.models._model_exception_base import (
    AttachmentNotSupportedError,
    ModelError,
)
from railtracks.llm.models.local.ollama import OllamaLLM

# TODO: Remove with the notices in 1.5.0.
pytestmark = pytest.mark.filterwarnings(r"ignore:.*in railtracks 1\.5\.0:FutureWarning")


@pytest.fixture
def mock_response():
    """Fixture for mocking successful API response"""
    mock = MagicMock()
    mock.json.return_value = {"models": [{"name": "test-model"}, {"name": "llama2"}]}
    mock.raise_for_status.return_value = None
    return mock


@pytest.fixture
def mock_failed_response():
    """Fixture for mocking failed API response"""
    mock = MagicMock()
    mock.raise_for_status.side_effect = requests.exceptions.RequestException(
        "Connection failed"
    )
    return mock


PDF_DATA_URI = (
    "data:application/pdf;base64,"
    + base64.b64encode(b"%PDF-1.4\n%fake pdf\n%%EOF").decode()
)
IMAGE_DATA_URI = "data:image/png;base64,iVBORw0KGgo="


def test_pdf_attachment_rejected(mock_response):
    """PDF attachments raise: litellm's Ollama transform drops them (#1628)."""
    with patch("requests.get", return_value=mock_response):
        ollama = OllamaLLM("test-model")
    message = UserMessage(content="Summarize this.", attachment=[PDF_DATA_URI])

    with pytest.raises(AttachmentNotSupportedError, match="application/pdf") as exc:
        ollama._to_litellm_message(message)
    assert isinstance(exc.value, ModelError)
    assert isinstance(exc.value, ValueError)


def test_pdf_in_history_fails_chat_before_completion(mock_response):
    """A PDF anywhere in the history fails the whole request without calling the model."""
    with patch("requests.get", return_value=mock_response):
        ollama = OllamaLLM("test-model")
    messages = MessageHistory(
        [
            UserMessage(
                content="Here is the paper.",
                attachment=[IMAGE_DATA_URI, PDF_DATA_URI],
            ),
            AssistantMessage(content="Got it."),
            UserMessage(content="Summarize it."),
        ]
    )

    with patch.object(litellm, "completion") as mock_completion:
        with pytest.raises(AttachmentNotSupportedError):
            ollama.chat(messages)
    mock_completion.assert_not_called()


def test_image_attachment_kept(mock_response):
    """Image attachments still serialize as image_url on Ollama."""
    with patch("requests.get", return_value=mock_response):
        ollama = OllamaLLM("test-model")
    message = UserMessage(content="View this image.", attachment=[IMAGE_DATA_URI])

    litellm_message = ollama._to_litellm_message(message)

    assert litellm_message["content"][1] == {
        "type": "image_url",
        "image_url": {"url": IMAGE_DATA_URI},
    }


def test_model_type():
    """Test the model_type class method"""
    assert OllamaLLM.model_gateway() == "Ollama"


def test_init_success(mock_response):
    """Test successful initialization of Ollama"""
    with patch("requests.get", return_value=mock_response):
        ollama = OllamaLLM("test-model")
        assert ollama.model_name() == "ollama_chat/test-model"
        assert ollama.domain == "http://localhost:11434"


def test_init_with_custom_domain(mock_response):
    """Test initialization with custom domain"""
    custom_domain = "http://custom-domain:11434"
    with patch("requests.get", return_value=mock_response):
        ollama = OllamaLLM("test-model", domain="custom", custom_domain=custom_domain)
        assert ollama.domain == custom_domain


def test_temperature_passed_to_litellm_completion(mock_response):
    """Assert that when OllamaLLM is created with temperature, it is passed to litellm.completion."""
    with patch("requests.get", return_value=mock_response):
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
    with patch("requests.get", return_value=mock_response):
        with pytest.raises(ProviderError) as exc_info:
            OllamaLLM("unavailable-model")
        assert "not available on server" in str(exc_info.value)


def test_init_connection_error(mock_failed_response):
    """Test initialization with connection error"""
    with patch("requests.get", return_value=mock_failed_response):
        with pytest.raises(requests.exceptions.RequestException):
            OllamaLLM("test-model")


def test_run_check_success(mock_response):
    """Test successful API check"""
    with patch("requests.get", return_value=mock_response):
        ollama = OllamaLLM("test-model")
        # Should not raise any exception
        ollama._run_check("api/tags")


def test_run_check_connection_error(mock_failed_response):
    """Test API check with connection error"""
    with patch(
        "requests.get",
        side_effect=requests.exceptions.RequestException("Connection failed"),
    ):
        with pytest.raises(requests.exceptions.RequestException):
            OllamaLLM("test-model")


def test_chat_with_tools_unsupported(mock_response):
    """Test chat_with_tools with unsupported model"""
    with patch("requests.get", return_value=mock_response):
        with patch.object(litellm, "supports_function_calling", return_value=False):
            ollama = OllamaLLM("test-model")
            messages = MessageHistory([UserMessage(content="test message")])
            tools = []

            with pytest.raises(ProviderError) as exc_info:
                ollama.chat_with_tools(messages, tools)
            assert "does not support function calling" in str(exc_info.value)


def test_model_name_extraction(mock_response):
    """Test model name extraction from full path"""
    with patch("requests.get", return_value=mock_response):
        ollama = OllamaLLM("ollama/test-model")
        assert ollama.model_name() == "ollama_chat/test-model"
        ollama2 = OllamaLLM("test-model")
        assert ollama2.model_name() == "ollama_chat/test-model"
        ollama3 = OllamaLLM("ollama_chat/test-model")
        assert ollama3.model_name() == "ollama_chat/test-model"


def test_init_with_auto_domain_missing_env(mock_response):
    """Test initialization with auto domain but missing environment variable"""
    with patch("requests.get", return_value=mock_response):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ProviderError) as exc_info:
                OllamaLLM("test-model", domain="auto")
            assert "OLLAMA_HOST environment variable not set" in str(exc_info.value)


def test_init_with_custom_domain_missing_env(mock_response):
    """Test initialization with custom domain but missing environment variable"""
    with patch("requests.get", return_value=mock_response):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ProviderError) as exc_info:
                OllamaLLM("test-model", domain="auto")
            assert "OLLAMA_HOST environment variable not set" in str(exc_info.value)


def test_init_with_default_domain(mock_response):
    """Test initialization with default domain setting"""
    with patch("requests.get", return_value=mock_response):
        ollama = OllamaLLM("test-model", domain="default")
        assert ollama.domain == "http://localhost:11434"


def test_init_with_auto_domain(mock_response):
    """Test initialization with auto domain"""
    custom_domain = "http://custom-domain:11434"
    with patch("requests.get", return_value=mock_response):
        with patch.dict(os.environ, {"OLLAMA_HOST": custom_domain}):
            ollama = OllamaLLM("test-model", domain="auto")
            assert ollama.domain == custom_domain


def test_init_with_custom_domain_missing_arg(mock_response):
    """Test initialization with custom domain but missing custom_domain argument"""
    with patch("requests.get", return_value=mock_response):
        with pytest.raises(ProviderError) as exc_info:
            OllamaLLM("test-model", domain="custom")
        assert "Custom domain must be provided" in str(exc_info.value)


def test_tools_survive_litellm_param_dropping(mock_response):
    """The routed model name must keep `tools` in the outgoing request (#1457)."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "f",
                "description": "d",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    with patch("requests.get", return_value=mock_response):
        ollama = OllamaLLM("test-model")
    provider, model = ollama.model_name().split("/", 1)
    optional_params = litellm.utils.get_optional_params(
        model=model, custom_llm_provider=provider, tools=tools
    )
    assert "tools" in optional_params


def test_function_calling_support_checked_against_catalog_name(mock_response):
    """The support check uses the `ollama/` prefix litellm's catalog is keyed on."""
    with patch("requests.get", return_value=mock_response):
        ollama = OllamaLLM("test-model")
    with patch(
        "railtracks.llm.models.local.ollama.supports_function_calling",
        return_value=True,
    ) as mock_supports:
        with patch.object(litellm, "completion") as mock_completion:
            mock_completion.return_value = litellm.utils.ModelResponse(
                choices=[{"message": {"content": "ok"}}]
            )
            ollama.chat_with_tools(MessageHistory([UserMessage(content="hi")]), [])
    assert mock_supports.call_args.kwargs["model"] == "ollama/test-model"
