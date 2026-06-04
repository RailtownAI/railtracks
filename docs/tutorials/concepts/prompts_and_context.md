# Prompts and Context Injection

Prompts are the primary interface between your application and an LLM. Railtracks lets you write prompts as **templates** with placeholders, then fill those placeholders at runtime from the session context — a feature called **context injection**.

---

## Why Context Injection?

Passing dynamic data to an LLM typically means one of two things: building prompt strings in application code, or appending additional user messages. Both approaches couple your prompt logic to your application logic and can inflate token usage.

Context injection separates concerns: the prompt is a static template that lives with the agent class; the runtime data lives in the context. The framework connects them automatically.

```text
system_message = "You are a {role} assistant for {company}."

# At runtime:
context = {"role": "billing", "company": "Acme Corp"}
# → "You are a billing assistant for Acme Corp."
```

This keeps agents reusable across sessions and scenarios without code changes.

---

## How It Works

Context injection uses Python's standard `str.format_map` style substitution with one practical difference: **unknown placeholders are left as-is** rather than raising a `KeyError`. This means a prompt with `{optional_value}` will not break if that key is absent from the context — it simply stays as `{optional_value}`.

### Placeholder syntax

Use `{key}` anywhere in a `SystemMessage` or `UserMessage` content string:

```python
"Today's date is {date}. The user's name is {name}."
```

### Escaping

To include a literal curly brace that should **not** be treated as a placeholder, double it:

```python
"Wrap your answer in {{code_block}} tags."
# → "Wrap your answer in {code_block} tags."
```

### What gets injected

Injection runs over every message in the history where `inject_prompt=True` (the default). Messages with non-string content (tool call results, structured outputs) are skipped automatically.

---

## Control Levels

Context injection can be turned off at four levels, from broadest to most granular. Each level is independent — you can mix and match.

### 1. Global level

Disables injection for all agents in the current process. Useful for testing or when you want injection off by default across an entire application.

```python
rt.set_config(prompt_injection=False)
```

### 2. Session / Flow level

Disables injection for a single session or flow run. Overrides the global default.

```python
with rt.Session(prompt_injection=False):
    ...

# or via Flow
rt.Flow("my-flow", entry_point=agent, prompt_injection=False)
```

### 3. LLM level (agent class)

Disables injection for a specific agent class, regardless of the session setting. The most targeted way to opt a particular agent out permanently.

```python
# Via the factory function
agent = rt.agent_node(
    system_message="Render {variable} literally.",
    llm=my_llm,
    context_injection=False,
)

# Via the NodeBuilder
builder.context_injection(False)

# Via class inheritance
class RawAgent(TerminalLLM):
    context_injection = False
```

### 4. Message level

Disables injection for one specific message while leaving all others enabled. The most granular option.

```python
# System message with injection (default)
system = rt.llm.SystemMessage("You are a {role} assistant.")

# User message without injection — e.g. to protect LaTeX expressions
user = rt.llm.UserMessage(r"Solve \frac{x}{2} = 4", inject_prompt=False)
```

A common use case: a maths assistant that injects the user's name via the system message but must not touch the user's input, which may contain `{` and `}` in equations.

### Level precedence

The LLM-level flag short-circuits session-level configuration: if `context_injection=False` is set on the agent class, the session's `prompt_injection` setting has no effect for that agent. Message-level control always wins for the individual message, regardless of all other settings.

| Level | Scope | API |
|---|---|---|
| Global | Entire process | `rt.set_config(prompt_injection=False)` |
| Session / Flow | One session run | `rt.Session(prompt_injection=False)` |
| LLM (agent class) | One agent class | `agent_node(context_injection=False)` |
| Message | One message | `UserMessage(..., inject_prompt=False)` |

---

## Setting Context Values

Values are read from the active session context at the moment the LLM is called — not when the agent is defined. Set them using `rt.context.put()` inside a session, or provide them up-front via `rt.Session(context={...})`:

```python
with rt.Session(context={"role": "billing", "company": "Acme"}):
    response = await rt.call(agent, user_input="Hello")
```

Values can also be updated mid-session with `rt.context.put("key", value)`, and the next LLM call will pick up the latest values.

---

## Related Topics

* [Walkthrough: Prompts and Context Injection](../walkthroughs/prompts_and_context.md) — code examples and reusable prompt templates
* [Context Management](../../documentation/advanced/context.md) — full reference for the context system
* [NodeBuilder](../../advanced_usage/node_builder.md) — building agent classes programmatically, including the `context_injection()` method
