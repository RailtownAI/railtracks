import pytest 
from railtracks.llm import OpenAILLM, GeminiLLM, AnthropicLLM, HuggingFaceLLM, CohereLLM
from railtracks.llm.history import MessageHistory
from railtracks.llm._exception_base import RTLLMError
from unittest.mock import patch


class TestInvalidModelNames:
    """Test invalid model names for each provider."""
    
    @pytest.mark.parametrize("provider_class,model_name", [
        (OpenAILLM, "claude-3-5-sonnet-20240620"),  # Anthropic model for OpenAI
        (AnthropicLLM, "gpt-4o"),  # OpenAI model for Anthropic
        (CohereLLM, "gpt-4o"),  # OpenAI model for Cohere
        (GeminiLLM, "gpt-4o"),  # OpenAI model for Gemini
        (OpenAILLM, "gemini-pro"),  # Gemini model for OpenAI
        (AnthropicLLM, "gemini-pro"),  # Gemini model for Anthropic
        (GeminiLLM, "claude-3-5-sonnet"),  # Anthropic model for Gemini
        (HuggingFaceLLM, "huggingface/meta-llama/Llama-3.3-70B-Instruct"),  # invalid naming structure for HuggingFace
        (HuggingFaceLLM, "meta-llama/Llama-3.3-70B-Instruct"),  # invalid naming structure for HuggingFace
    ])
    def test_invalid_model_names(self, provider_class, model_name):
        """Test that wrong model names raise LLMError."""
        # Determine what provider the model actually belongs to
        provider_mapping = {
            "claude": "anthropic",
            "gpt": "openai", 
            "gemini": "vertex_ai"
        }
        
        # Guess the actual provider based on model name
        actual_provider = None
        for key, value in provider_mapping.items():
            if key in model_name.lower():
                actual_provider = value
                break
        
        if actual_provider:
            with patch('railtracks.llm.models.api_providers._provider_wrapper.get_llm_provider') as mock_provider:
                # Return the actual provider, which should mismatch with the class being tested
                mock_provider.return_value = ("something", actual_provider, "info")
                
                with pytest.raises(RTLLMError):
                    _ = provider_class(model_name)


class TestFunctionCallingSupport:
    """Test function calling support for each provider."""
    
    @pytest.mark.parametrize("provider_class, model_name, expected_provider", [
        (OpenAILLM, "openai/ada-001", "openai"),
        (AnthropicLLM, "anthropic/claude-v1", "anthropic"),
        (GeminiLLM, "gemini/gemini-2.0-flash-exp-image-generation", "vertex_ai"),   # gemini models return "vertex_ai" as the provider when we call get_llm_provider
        (CohereLLM, "cohere/command-a-03-2025", "cohere_chat"),
    ])
    def test_no_function_calling_support(self, provider_class, model_name, expected_provider):
        """Test that models without function calling support raise appropriate errors."""
        with patch('railtracks.llm.models.api_providers._provider_wrapper.get_llm_provider') as mock_provider:
            # Mock valid provider response
            mock_provider.return_value = ("something", expected_provider, "info")
            
            with patch('litellm.supports_function_calling', return_value=False):
                model = provider_class(model_name)
                assert model is not None
                
                with pytest.raises(RTLLMError, match="does not support function calling"):
                    model.chat_with_tools(MessageHistory([]), [])

