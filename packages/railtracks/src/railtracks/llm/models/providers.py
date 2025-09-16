
"""
Defines the supported model providers for LLM integrations in RailTracks.

This enum is used to specify which external LLM provider (such as OpenAI, Anthropic, Gemini, etc.)
is being referenced or configured in the system. Use these values to ensure type safety and
consistency when selecting or switching between providers.
"""

from enum import Enum

class ModelProvider(str, Enum):
    """
    Enum of supported LLM model providers for RailTracks.
    """
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    HUGGINGFACE = "huggingface"
    AZUREAI = "AzureAI"
    OLLAMA = "Ollama"