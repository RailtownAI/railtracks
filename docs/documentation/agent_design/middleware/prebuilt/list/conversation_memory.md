# ConversationMemory

`ConversationMemory` automatically preserves and appends conversation history across successive node invocations.


By default, an `agent_node` is stateless: each invocation is isolated. Attaching `ConversationMemory` causes previous conversational turns to be remembered and prepended to new user inputs automatically.

```python
--8<-- "docs/scripts/prebuilt_middleware.py:conversation_memory"
```

## How It Works

1. On the first turn, the user message is sent to the model normally, and the resulting message history is cached in the active session context (`rt.context`) under `memory.context_key`.
2. By default, each `ConversationMemory` instance generates a unique, isolated session context key (e.g. `conversation_history_a1b2c3d4`). This ensures multiple agents running in the same flow each have their own independent conversation memory by default.
3. On subsequent turns, the prior message history is retrieved from the session context, the incoming user input is appended, and the accumulated history is passed to the agent.
4. The session context variable is automatically updated after every turn, accumulating multi-turn conversation context.

## Multi-Agent Isolation & Configuration

- **Automatic Per-Instance Isolation**: Each `ConversationMemory()` instance has its own unique session context key by default. Two agents in the same flow maintain completely independent memory stores with zero extra configuration.
- **Custom Context Key**: Pass an explicit `context_key` to assign a known session variable name:
  ```python
  memory = ConversationMemory(context_key="researcher_memory")
  ```
- **Shared Memory Between Agents**: If you want multiple agents to share a common conversation history, pass the same explicit `context_key` or instance:
  ```python
  shared_memory = ConversationMemory(context_key="team_chat")
  agent1 = rt.agent_node("AgentA", llm=model, middleware=[shared_memory])
  agent2 = rt.agent_node("AgentB", llm=model, middleware=[shared_memory])
  ```
- **Session Context Inspection**: You can inspect an agent's history directly via `rt.context.get(memory.context_key)`, `session.context[memory.context_key]`, or `memory.get_history()`.
- **Preloading History**: You can seed conversation history by pre-populating the session context:
  ```python
  with rt.Session(context={"team_chat": initial_history}):
      await flow.ainvoke("Follow up question")
  ```
- **Max Messages**: Pass `max_messages=10` to prune history to the most recent $N$ messages and avoid exceeding model context windows.
- **Clearing Memory**: Call `memory.clear()` to wipe the stored history from both the instance and the active session context.

