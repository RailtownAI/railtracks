import railtracks as rt

ChatAgent = rt.agent_node(
    name="ChatAgent",
    system_message="Answer clearly and remember details from the conversation.",
    llm=rt.llm.OpenAILLM("gpt-5.1"),
)


# --8<-- [start: direct_handoff]
async def direct_conversation() -> str:
    history = rt.llm.MessageHistory(
        [rt.llm.UserMessage("My deployment region is eu-west-1.")]
    )
    first_response = await rt.call(ChatAgent, history)

    next_history = rt.llm.MessageHistory(first_response.message_history)
    next_history.append(rt.llm.UserMessage("Which region did I mention?"))
    second_response = await rt.call(ChatAgent, next_history)
    return second_response.text


# --8<-- [end: direct_handoff]


# --8<-- [start: context_handoff]
@rt.function_node
async def conversation_turn(user_message: str) -> str:
    """Continue the run's conversation with one user message."""
    saved_history: rt.llm.MessageHistory = rt.context.get(
        "conversation_history", rt.llm.MessageHistory()
    )
    history = rt.llm.MessageHistory(saved_history)
    history.append(rt.llm.UserMessage(user_message))

    response = await rt.call(ChatAgent, history)
    rt.context.put("conversation_history", response.message_history)
    return response.text


@rt.function_node
async def two_turn_conversation() -> str:
    """Run two agent turns that share history through context."""
    await rt.call(conversation_turn, "My deployment region is eu-west-1.")
    return await rt.call(conversation_turn, "Which region did I mention?")


conversation_flow = rt.Flow(
    name="conversation-flow",
    entry_point=two_turn_conversation,
)
# --8<-- [end: context_handoff]
