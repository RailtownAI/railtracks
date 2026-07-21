import railtracks as rt

llm_map = {
    "openai": rt.llm.OpenAILLM("gpt-4o"),
    "anthropic": rt.llm.AnthropicLLM("claude-sonnet-4-5-20250929"),
    "huggingface": rt.llm.HuggingFaceLLM("together/deepseek-ai/DeepSeek-R1"),        # this model is a little dumb, see test_function_as_tool test case
    "gemini": rt.llm.GeminiLLM("gemini-2.5-flash"),
    # "cohere": rt.llm.CohereLLM("command-a-03-2025"), # TODO: #uncomment after https://github.com/RailtownAI/railtracks/issues/775
}

