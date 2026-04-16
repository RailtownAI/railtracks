import railtracks as rt

SimpleChatAgent = rt.agent_node(
    name="SimpleChatAgent",
    system_message="You are Clippy, a helpful assistant that provides answers to user questions.",
    llm=rt.llm.GeminiLLM("gemini-3-flash-preview")
)