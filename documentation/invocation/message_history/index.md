# Message History

Each call is stateless: Railtracks does not automatically send an earlier conversation to the next call. An agent response includes the conversation in `response.message_history`, preserving any system messages supplied by the caller while excluding the target agent's configured system message. Railtracks prepends the configured system message on each call, so passing the returned history back does not accumulate duplicate system messages.

The examples below use this agent:

```python
import railtracks as rt

ChatAgent = rt.agent_node(
    name="ChatAgent",
    system_message="Answer clearly and remember details from the conversation.",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
)
```

## Continue a conversation across calls

Copy the returned history, append the next user message, and pass it to the agent again:

```python
async def direct_conversation() -> str:
    history = rt.llm.MessageHistory(
        [rt.llm.UserMessage("My deployment region is eu-west-1.")]
    )
    first_response = await rt.call(ChatAgent, history)

    next_history = rt.llm.MessageHistory(first_response.message_history)
    next_history.append(rt.llm.UserMessage("Which region did I mention?"))
    second_response = await rt.call(ChatAgent, next_history)
    return second_response.content
```

`MessageHistory` behaves like a list. Copying the returned history before appending keeps the earlier response snapshot unchanged. Passing only `response.content` gives the next agent the previous answer without the messages that led to it.

## Share history between nodes in one run

When several nodes in the same flow need the conversation, store the latest history in [global context](https://docs.railtracks.org/documentation/advanced/context/index.md). The context is available to every node in that run:

```python
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
    return response.content


@rt.function_node
async def two_turn_conversation() -> str:
    """Run two agent turns that share history through context."""
    await rt.call(conversation_turn, "My deployment region is eu-west-1.")
    return await rt.call(conversation_turn, "Which region did I mention?")


conversation_flow = rt.Flow(
    name="conversation-flow",
    entry_point=two_turn_conversation,
)
```

This get → copy → append → put pattern assumes one turn at a time; concurrent turns must use separate context keys or synchronize access so one turn does not overwrite another turn's history.

Context ends with the run. If separate `flow.invoke(...)` or `flow.ainvoke(...)` calls should share a conversation, keep the latest `message_history` in your application or durable storage and pass it into the next run explicitly.
