import railtracks as rt

llm_map = {
    "openai": rt.llm.OpenAILLM("gpt-6-luna"),
    "anthropic": rt.llm.AnthropicLLM("claude-haiku-5-5"),
    "gemini": rt.llm.GeminiLLM("gemini-3.5-flash-lite"),
}
