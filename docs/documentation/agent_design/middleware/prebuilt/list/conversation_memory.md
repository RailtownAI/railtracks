# ConversationMemory

`ConversationMemory` automatically preserves and appends conversation history across successive node invocations.


By default, an `agent_node` is stateless: each invocation is isolated. Attaching `ConversationMemory` causes previous conversational turns to be remembered and prepended to new user inputs automatically.

```python
--8<-- "docs/scripts/prebuilt_middleware.py:conversation_memory"
```

## How It Works

1. On the first turn, the user message is sent to the model normally, and the resulting message history is saved in the active session context (`rt.context`) under `context_key` (defaulting to `"conversation_history"`).
2. On subsequent turns, the prior message history is retrieved from the session context, the incoming user input is appended, and the accumulated history is passed to the agent.
3. The session context variable is automatically updated after every turn, accumulating multi-turn conversation context.

## Session Context & Configuration

- **Session Context Injection**: History is injected directly into `rt.context` under `context_key="conversation_history"` by default. You can inspect or access it via `rt.context.get("conversation_history")`, `session.context["conversation_history"]`, or `connection.context["conversation_history"]`.
- **Preloading History**: You can seed conversation history by pre-populating the session context:
  ```python
  with rt.Session(context={"conversation_history": initial_history}):
      await flow.ainvoke("Follow up question")
  ```
- **Custom Context Key**: Pass `context_key="my_chat_history"` to isolate multiple conversational agents or customize the session variable name.
- **Max Messages**: Pass `max_messages=10` to prune history to the most recent $N$ messages and avoid exceeding model context windows.
- **Clearing Memory**: Call `memory.clear()` to wipe the stored history from both the instance and the active session context.

