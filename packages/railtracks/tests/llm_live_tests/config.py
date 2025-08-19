import pytest
import railtracks as rt

llm_map = {
    "openai": rt.llm.OpenAILLM("gpt-4o"),
    "anthropic": rt.llm.AnthropicLLM("claude-3-5-sonnet-20241022"),
    "huggingface": rt.llm.HuggingFaceLLM("featherless-ai/mistralai/Mistral-7B-Instruct-v0.2"),
    "gemini": rt.llm.GeminiLLM("gemini-2.5-flash"),
}