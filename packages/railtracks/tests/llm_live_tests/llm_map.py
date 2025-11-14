import railtracks as rt

llm_map = {
    "openai": rt.llm.OpenAILLM("gpt-4o"),
    "anthropic": rt.llm.AnthropicLLM("claude-sonnet-4-5-20250929"),
    "huggingface": rt.llm.HuggingFaceLLM("cerebras/Qwen/Qwen3-32B"),        # this model is a little dumb, see test_function_as_tool test case
    "gemini": rt.llm.GeminiLLM("gemini-2.5-flash"),
    "cohere": rt.llm.CohereLLM("command-a-03-2025"),
    "openai_stream": rt.llm.OpenAILLM("gpt-4o", stream=True),
    "anthropic_stream": rt.llm.AnthropicLLM("claude-sonnet-4-5-20250929", stream=True),
    "huggingface_stream": rt.llm.HuggingFaceLLM("cerebras/Qwen/Qwen3-32B", stream=True),        # this model is a little dumb, see test_function_as_tool test case
    "gemini_stream": rt.llm.GeminiLLM("gemini-2.5-flash", stream=True),
    "cohere_stream": rt.llm.CohereLLM("command-a-03-2025", stream=True),
}

