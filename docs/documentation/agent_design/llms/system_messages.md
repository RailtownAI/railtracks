# System Messages

A system message can reach a model two ways in Railtracks, and they behave differently on purpose. The `system_message=` argument on `rt.agent_node` is part of the **agent's configuration**: it describes who that agent is, and Railtracks sends it on every invocation. A `SystemMessage` you place in a `MessageHistory` is part of the **conversation**: it belongs to the caller, and Railtracks leaves it exactly where you put it.

```python
import railtracks as rt

# Configuration: sent on every call to this agent.
agent = rt.agent_node(
    "Assistant",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are terse.",
)

# Conversation: part of the history the caller owns.
history = rt.llm.MessageHistory(
    [
        rt.llm.SystemMessage("Var A = 123"),
        rt.llm.UserMessage("What is Var A?"),
    ]
)
```

## What gets sent

The agent's own system message is always placed first. System messages already in the history keep their position and their order relative to each other.

| You provide | Sent to the model |
|---|---|
| `system_message=` only | `[agent prompt, ...history]` |
| A `SystemMessage` in the history | `[...history]`, unchanged |
| Both | `[agent prompt, ...history]`, the history's own system messages untouched |
| Several `SystemMessage`s in the history | All of them, in the order you wrote them |

Passing both is not a conflict and neither one is discarded. The agent's prompt goes first because it establishes the agent's identity, and the conversation's own system turns follow in place.

## What comes back

`response.message_history` is the conversation, so it contains every system message the caller put there, and **not** the agent's own configured prompt. That makes the returned history safe to feed straight back in for the next turn.

```python
response = await rt.call(agent, history)

next_turn = response.message_history
next_turn.append(rt.llm.UserMessage("And Var B?"))

response = await rt.call(agent, next_turn)
```

The agent's prompt is re-attached on every call rather than accumulating in the history, so a conversation that runs for fifty turns still sends exactly one copy of it. Because the returned history omits that prompt, handing it to a *different* agent gives you that agent's prompt instead of the first one's, rather than both.

If you need to see the exact list of messages that went to the provider, including the agent's own prompt, read it from the run's recorded events rather than from the response.

## Multiple system messages

An OpenAI-format history may legally contain more than one system turn, and Railtracks passes them all through in order. Providers do not agree on what a system message in the *middle* of a conversation means:

| Provider | Behaviour |
|---|---|
| OpenAI and OpenAI-compatible | The message stays at the index you placed it. |
| Anthropic | Every system message is hoisted into the request's top-level `system` field, in order, and removed from the message list. Position is not preserved. |
| Gemini | Same as Anthropic: hoisted to a dedicated system instruction. |

Railtracks logs a warning when a system message follows a non-system message, because that is the shape whose meaning changes between providers. Leading system messages, however many, are portable and never warn.

## Warnings you may see

| Warning | Cause |
|---|---|
| `No SystemMessage was provided` | Neither the agent nor the history supplies one anywhere. |
| `Only SystemMessage was provided` | The history has no user turn for the model to answer. |
| `A SystemMessage appears after a non-system message` | A mid-conversation system turn, which is handled differently per provider (see above). |
