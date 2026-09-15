# ConversationMemory

`ConversationMemory` automatically preserves and appends conversation history across successive node invocations.


By default, an `agent_node` is stateless: each invocation is isolated. Attaching `ConversationMemory` causes previous conversational turns to be remembered and prepended to new user inputs automatically.

```python
--8<-- "docs/scripts/prebuilt_middleware.py:conversation_memory"
```

## How It Works

1. On the first turn, the user message is sent to the model normally, and the resulting message history is saved in the memory store.
2. On subsequent turns, the prior message history is fetched from the store, the new user input is appended as a `UserMessage`, and the combined history is passed to the agent.
3. The store updates after every turn, accumulating multi-turn conversation context.

## Scoping & Isolation

- **Default Global Store**: By default, memories are held in a module-level dictionary (`GLOBAL_CONVERSATION_STORE`) under the key `"default"`.
- **Session Keys**: Pass `session_key="user_123"` (or a zero-argument callable like `session_key=lambda: rt.context.get("user_id")`) to separate conversations by user or session ID.
- **Custom Stores**: Pass `store={}` to give an agent instance its own isolated storage dictionary instead of the global store.
- **Max Messages**: Pass `max_messages=10` to prune history to the most recent N messages and avoid exceeding model context windows.
- **Clearing Memory**: Call `memory.clear()` to wipe all stored history, or `memory.clear("user_123")` for a specific session.
