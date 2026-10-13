"""The models the live tests run against: each provider's cheapest current tier.

``test_llm_map_freshness.py`` fails when one of these leaves its provider's catalog or
is about to be deprecated, which is the cue to bump it here.
"""

import railtracks as rt

llm_map = {
    "openai": rt.llm.OpenAILLM("gpt-6-luna"),
    "anthropic": rt.llm.AnthropicLLM("claude-haiku-5-5"),
    "huggingface": rt.llm.HuggingFaceLLM("together/meta-llama/Llama-3.3-70B-Instruct"),
    "gemini": rt.llm.GeminiLLM("gemini-3.5-flash-lite"),
}
