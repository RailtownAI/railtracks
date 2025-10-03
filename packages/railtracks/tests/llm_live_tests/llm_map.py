import railtracks as rt

llm_map = {
    "openai": rt.llm.OpenAILLM("gpt-4o"),
    "anthropic": rt.llm.AnthropicLLM("claude-3-5-sonnet-20241022"),
    "huggingface": rt.llm.HuggingFaceLLM("cerebras/Qwen/Qwen3-32B"),        # this model is a little dumb, see test_function_as_tool test case
    "gemini": rt.llm.GeminiLLM("gemini-2.5-flash"),
    "cohere": rt.llm.CohereLLM("command-a-03-2025"),
}