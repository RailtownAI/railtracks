# ConversationMemory

`ConversationMemory` automatically preserves and appends conversation history across successive node invocations.


By default, an `agent_node` is stateless: each invocation is isolated. Attaching `ConversationMemory` causes previous conversational turns to be remembered and prepended to new user inputs automatically.

```python
--8<-- "docs/scripts/prebuilt_middleware.py:conversation_memory"
```

## How It Works

1. On the first turn, the user message is sent to the model normally, and the resulting message history is cached in the active session context (`rt.context`) under `memory.context_key`.
2. When attached to an agent (e.g. `rt.agent_node("Researcher", middleware=[ConversationMemory()])`), `context_key` is automatically namespaced to `conversation_history_<AgentName>` (e.g. `"conversation_history_Researcher"`). This ensures multiple agents running in the same flow each have their own isolated conversation memory.
3. On subsequent turns, the prior message history is retrieved from the session context, the incoming user input is appended, and the accumulated history is passed to the agent.
4. The session context variable is automatically updated after every turn, accumulating multi-turn conversation context.

## Multi-Agent Isolation & Configuration

- **Automatic Agent Namespacing**: When attached to an `agent_node`, `ConversationMemory` automatically names the session context variable after the agent (e.g. `conversation_history_Researcher` and `conversation_history_Writer`). Two agents in the same flow maintain completely independent memory stores with zero configuration.
- **Shared Memory Between Agents**: If you want multiple agents to share a common conversation history, pass the same explicit `context_key`:
  ```python
  shared_memory = ConversationMemory(context_key="team_chat")
  agent1 = rt.agent_node("AgentA", llm=model, middleware=[shared_memory])
  agent2 = rt.agent_node("AgentB", llm=model, middleware=[shared_memory])
  ```
- **Session Context Inspection**: You can inspect an agent's history directly via `rt.context.get(memory.context_key)`, `session.context[memory.context_key]`, or `memory.get_history()`.
- **Preloading History**: You can seed conversation history by pre-populating the session context using either the namespaced key or the generic `"conversation_history"` fallback:
  ```python
  with rt.Session(context={"conversation_history_Researcher": initial_history}):
      await flow.ainvoke("Follow up question")
  ```
- **Max Messages**: Pass `max_messages=10` to prune history to the most recent $N$ messages and avoid exceeding model context windows.
- **Clearing Memory**: Call `memory.clear()` to wipe the stored history from both the instance and the active session context.

