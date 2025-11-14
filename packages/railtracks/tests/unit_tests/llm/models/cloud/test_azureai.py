import pytest
import litellm
from unittest.mock import patch

from railtracks.llm.models import AzureAILLM
from railtracks.llm._exception_base import RTLLMError
from railtracks.llm.models._litellm_wrapper import LiteLLMWrapper

from railtracks.llm.response import Response
from railtracks.llm.message import AssistantMessage


MODEL_NAME = "deepseek-r1"
TEST_CHAT_MODEL_NAME = "azure_ai/deepseek-r1"
TEST_TOOLCALLING_MODEL_NAME = "azure_ai/deepseek-v3-0324"


@pytest.fixture
def response():
    """Fixture to provide a mock response for testing"""
    return Response(
        message=AssistantMessage("This is a response with no tool calls."),
    )


def test_model_type():
    """Test if the model type is correctly returned"""
    assert AzureAILLM.model_gateway() == "AzureAI"


def test_init_success():
    """Test successful initialization of AzureAILLM"""
    llm = AzureAILLM(model_name=TEST_CHAT_MODEL_NAME)
    assert llm._model_name == TEST_CHAT_MODEL_NAME


def test_init_model_not_available():
    """Test initialization with a model that is not available"""
    with pytest.raises(RTLLMError, match="Model 'non_existent_model' is not available"):
        AzureAILLM(model_name="non_existent_model")


def test_chat_success(message_history):
    """Test successful chat response from AzureAILLM"""
    llm = AzureAILLM(model_name=TEST_CHAT_MODEL_NAME)

    with patch.object(
        litellm,
        "completion",
        return_value=litellm.utils.ModelResponse(
            choices=[{"message": {"content": "This is a response from Azure AI."}}]
        ),
    ):
        response = llm.chat(message_history)
        assert response.message.content == "This is a response from Azure AI."


def test_chat_failure(message_history):
    """Test handling of chat failure due to an internal server error"""
    llm = AzureAILLM(model_name=TEST_CHAT_MODEL_NAME)

    with patch.object(
        litellm,
        "completion",
        side_effect=litellm.InternalServerError(
            "Internal server error", "azure_ai", MODEL_NAME
        ),
    ):
        with pytest.raises(
            RTLLMError, match="Azure AI LLM error while processing the request"
        ):
            llm.chat(message_history)


def test_chat_with_tools_success(message_history, response, tool):
    """
    Test successful chat with tools response from AzureAILLM
    Note there is no need to test for actual tool invocations
    """
    llm = AzureAILLM(model_name=TEST_TOOLCALLING_MODEL_NAME)

    with patch.object(LiteLLMWrapper, "chat_with_tools", return_value=response):
        response = llm.chat_with_tools(message_history, [tool])
        assert response.message.content == "This is a response with no tool calls."


def test_chat_with_tools_failure(message_history, tool):
    """"""
    llm = AzureAILLM(model_name=TEST_CHAT_MODEL_NAME)

    with patch.object(litellm, "supports_function_calling", return_value=False):
        with pytest.raises(RTLLMError):
            llm.chat_with_tools(message_history, [tool])
