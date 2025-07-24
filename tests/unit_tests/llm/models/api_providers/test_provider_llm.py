import pytest 
from railtracks.llm import OpenAILLM, GeminiLLM, AnthropicLLM
from railtracks.llm.history import MessageHistory
from railtracks.exceptions import LLMError
from unittest.mock import patch

model_map = {
    "openai": OpenAILLM,
    "anthropic": AnthropicLLM,
    "gemini": GeminiLLM,
}

class TestProviderLLMWrapper:
    
    @pytest.mark.parametrize("provider, model_name, mock_provider_return, should_succeed", [
        # Valid cases - provider matches expected
        ("openai", "openai/gpt-3.5-turbo", "openai", True),
        ("openai", "openai/gpt-4", "openai", True),
        ("anthropic", "anthropic/claude-3-5-sonnet", "anthropic",  True),
        ("gemini", "gemini/gemini-2.5-flash", "gemini", True),
        
        # Invalid cases - provider mismatch
        ("openai", "claude-3-5-sonnet", "anthropic", False),  # Anthropic model with OpenAI class
        ("anthropic", "gpt-4o", "openai", False),  # OpenAI model with Anthropic class
        ("gemini", "gpt-4o", "openai", False),  # OpenAI model with Gemini class
    ])
    def test_provider_validation(self, provider, model_name, mock_provider_return, should_succeed):
        """Parametrized test for different model/provider combinations."""
        with patch('railtracks.llm.models.api_providers._provider_wrapper.get_llm_provider') as mock_provider:
            # Mock the return value: (model_info, provider_name, other_info)
            mock_provider.return_value = ("something", mock_provider_return, "info")
            
            model_class = model_map.get(provider)
            
            if should_succeed:
                model = model_class(model_name)
                assert model is not None
            else:
                with pytest.raises(LLMError, match="Invalid model name"):
                    _ = model_class(model_name)

    @pytest.mark.parametrize("provider,model_name,supports_function_calling", [
        ("openai", "openai/ada-001", False),
        ("anthropic", "anthropic/claude-v1", False),
        ("gemini", "gemini/gemini-2.5-flash", False),
    ])
    def test_no_function_calling(self, provider, model_name, supports_function_calling):
        """Test that chat_with_tools raises an error when the model does not support function calling."""
        provider_name_map = {
            "openai": "openai",
            "anthropic": "anthropic", 
            "gemini": "vertex_ai"  # Gemini typically uses vertex_ai provider
        }
        
        with patch('railtracks.llm.models.api_providers._provider_wrapper.get_llm_provider') as mock_provider:
            # Mock valid provider response
            mock_provider.return_value = ("something", provider_name_map[provider], "info")
            
            with patch('litellm.supports_function_calling', return_value=supports_function_calling):
                model_class = model_map.get(provider)
                model = model_class(model_name)
                assert model is not None
                
                with pytest.raises(LLMError, match="does not support function calling"):
                    model.chat_with_tools(MessageHistory([]), [])

    @pytest.mark.parametrize("provider, model_name", [
        ("openai", "invalid-openai-model"),
        ("anthropic", "invalid-anthropic-model"),
        ("gemini", "invalid-gemini-model"),
    ])
    def test_model_not_found_error(self, provider, model_name):
        """Test that ModelNotFoundError is raised when get_llm_provider throws an exception."""
        with patch('railtracks.llm.models.api_providers._provider_wrapper.get_llm_provider') as mock_provider:
            # Mock get_llm_provider to raise an exception
            mock_provider.side_effect = Exception("Model not found in provider list")
            
            model_class = model_map.get(provider)
            with pytest.raises(LLMError):  # This should raise ModelNotFoundError, which inherits from LLMError
                _ = model_class(model_name)


class TestInvalidModelNames:
    """Test invalid model names for each provider."""
    
    @pytest.mark.parametrize("provider_class,model_name", [
        (OpenAILLM, "claude-3-5-sonnet-20240620"),  # Anthropic model for OpenAI
        (AnthropicLLM, "gpt-4o"),  # OpenAI model for Anthropic
        (GeminiLLM, "gpt-4o"),  # OpenAI model for Gemini
        (OpenAILLM, "gemini-pro"),  # Gemini model for OpenAI
        (AnthropicLLM, "gemini-pro"),  # Gemini model for Anthropic
        (GeminiLLM, "claude-3-5-sonnet"),  # Anthropic model for Gemini
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
                
                with pytest.raises(LLMError, match="Invalid model name"):
                    _ = provider_class(model_name)


class TestFunctionCallingSupport:
    """Test function calling support for each provider."""
    
    @pytest.mark.parametrize("provider_class, model_name, expected_provider", [
        (OpenAILLM, "openai/ada-001", "openai"),
        (AnthropicLLM, "anthropic/claude-v1", "anthropic"),
        (GeminiLLM, "gemini/gemini-2.0-flash-exp-image-generation", "gemini"),
    ])
    def test_no_function_calling_support(self, provider_class, model_name, expected_provider):
        """Test that models without function calling support raise appropriate errors."""
        with patch('railtracks.llm.models.api_providers._provider_wrapper.get_llm_provider') as mock_provider:
            # Mock valid provider response
            mock_provider.return_value = ("something", expected_provider, "info")
            
            with patch('litellm.supports_function_calling', return_value=False):
                model = provider_class(model_name)
                assert model is not None
                
                with pytest.raises(LLMError, match="does not support function calling"):
                    model.chat_with_tools(MessageHistory([]), [])


# If you want to keep it simple and close to your original structure:
class TestSimpleParametrized:
    
    @pytest.mark.parametrize("test_case", [
        # Format: (provider_class, model_name, mock_provider_return, should_succeed, test_type)
        (OpenAILLM, "openai/gpt-3.5-turbo", "openai", True, "valid"),
        (OpenAILLM, "claude-3-5-sonnet-20240620", "anthropic", False, "invalid"),
        (AnthropicLLM, "anthropic/claude-3-5-sonnet", "anthropic", True, "valid"),
        (AnthropicLLM, "gpt-4o", "openai", False, "invalid"),
        (GeminiLLM, "gemini/gemini-2.5-flash", "vertex_ai", True, "valid"),
        (GeminiLLM, "gpt-4o", "openai", False, "invalid"),
    ])
    def test_model_initialization(self, test_case):
        """Test model initialization with various scenarios."""
        provider_class, model_name, mock_provider_return, should_succeed, test_type = test_case
        
        with patch('railtracks.llm.models.api_providers._provider_wrapper.get_llm_provider') as mock_provider:
            mock_provider.return_value = ("something", mock_provider_return, "info")
            
            if should_succeed:
                model = provider_class(model_name)
                assert model is not None
            else:
                with pytest.raises(LLMError, match="Invalid model name"):
                    _ = provider_class(model_name)