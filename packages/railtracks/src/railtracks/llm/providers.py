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

    Attributes:
        OPENAI: OpenAI models (e.g., GPT-3, GPT-4).
        ANTHROPIC: Anthropic models (e.g., Claude).
        GEMINI: Google Gemini models.
        HUGGINGFACE: HuggingFace-hosted models.
        AZUREAI: Azure OpenAI Service models.
        OLLAMA: Ollama local LLMs.
        COHERE: Cohere models.
    """

    OPENAI = "OpenAI"
    ANTHROPIC = "Anthropic"
    GEMINI = "Vertex_AI"
    HUGGINGFACE = "HuggingFace"
    AZUREAI = "AzureAI"
    OLLAMA = "Ollama"
    COHERE = "cohere_chat"
    TELUS = "Telus"
    PORTKEY = "PortKey"
    UNKNOWN = "Unknown"


# Providers we do not support token streaming for when tool calling is involved. A streamed
# invocation that reaches one of these providers with tools attached falls back to a buffered
# model call (with a warning) — the final response is unaffected, only incremental chunks are
# skipped.
TOOL_CALLING_STREAMING_BLACKLIST = frozenset(
    {
        ModelProvider.ANTHROPIC,
        ModelProvider.AZUREAI,
        ModelProvider.GEMINI,
        ModelProvider.OLLAMA,
        ModelProvider.HUGGINGFACE,
    }
)
