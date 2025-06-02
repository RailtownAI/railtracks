import pytest
from src.requestcompletion.llm import AnthropicLLM
from src.requestcompletion.llm.history import MessageHistory

def test_anthropic_llm_correct_init():
    """
    Test that AnthropicLLM initializes correctly with a valid model name.
    """
    model = AnthropicLLM("claude-3-sonnet-20240229")
    assert model is not None

def test_anthropic_llm_no_function_calling():
    """
    Test that chat_with_tools raises an error when the model does not support function calling.
    """
    model = AnthropicLLM("anthropic/claude-v1")
    assert model is not None
    with pytest.raises(ValueError, match="does not support function calling"):
        model.chat_with_tools(MessageHistory([]), [])

def test_anthropic_llm_invalid_model_name():
    """
    Test that AnthropicLLM raises an error for an invalid model name.
    """
    with pytest.raises(ValueError, match="Invalid model name"):
        _ = AnthropicLLM("gpt-4o")