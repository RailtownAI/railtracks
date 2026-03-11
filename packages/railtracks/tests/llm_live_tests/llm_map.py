import railtracks as rt

llm_map = {
    "openai": rt.llm.OpenAILLM("gpt-4o"),
    "openai_stream": rt.llm.OpenAILLM("gpt-4o", stream=True),
    "anthropic": rt.llm.AnthropicLLM("claude-sonnet-4-5-20250929"),
    "huggingface": rt.llm.HuggingFaceLLM("together/deepseek-ai/DeepSeek-R1"),        # this model is a little dumb, see test_function_as_tool test case
    "gemini": rt.llm.GeminiLLM("gemini-2.5-flash"),
    "anthropic_stream": rt.llm.AnthropicLLM("claude-sonnet-4-5-20250929", stream=True),
    # "cohere": rt.llm.CohereLLM("command-a-03-2025"), # TODO: #uncomment after https://github.com/RailtownAI/railtracks/issues/775
    "huggingface_stream": rt.llm.HuggingFaceLLM("together/deepseek-ai/DeepSeek-R1", stream=True),        # this model is a little dumb, see test_function_as_tool test case
    "gemini_stream": rt.llm.GeminiLLM("gemini-2.5-flash", stream=True),
    # "cohere_stream": rt.llm.CohereLLM("command-a-03-2025", stream=True), #TODO: #uncomment after https://github.com/RailtownAI/railtracks/issues/775
}

