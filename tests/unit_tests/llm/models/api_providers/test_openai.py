import pytest
from railtracks.llm import OpenAILLM
from railtracks.llm.history import MessageHistory
from railtracks.exceptions import LLMError


def test_llm_correct_init():
    """
    Test that OpenAI initializes correctly with a valid model name.
    """
    model = OpenAILLM("gpt-4o")
    assert model is not None

def test_llm_no_function_calling():
    """
    Test that chat_with_tools raises an error when the model does not support function calling.
    """
    model = OpenAILLM("openai/ada-001")
    assert model is not None
    with pytest.raises(LLMError, match="does not support function calling"):
        model.chat_with_tools(MessageHistory([]), [])

def test_llm_invalid_model_name():
    """
    Test that OpenAI raises an error for an invalid model name.
    """
    with pytest.raises(LLMError, match="Invalid model name"):
        _ = OpenAILLM("claude-3-sonnet-20240229")