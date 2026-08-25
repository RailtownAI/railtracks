# Add Middleware to a Railtracks Agent or Node

The user wants to add middleware to a railtracks node/agent: $ARGUMENTS

## Quick reference

| Decorator | Signature | Slot | Fires on failure? |
|---|---|---|---|
| `rt.wrap_node` | `async fn(call, *args, **kwargs) -> result` | `middleware=` or `model_middleware=` | Yes — you control the try/except |
| `rt.wrap_llm` | `async fn(llm_call, message_history, schema, tools) -> Response` | `model_middleware=` only | Yes |
| `rt.before_llm` | `fn(message_history, schema, tools) -> (message_history, schema, tools)` (sync or async) | `model_middleware=` only | N/A (runs before the call) |
| `rt.after_llm` | `fn(response) -> response` (sync or async) | `model_middleware=` only | No — skipped on exception |
| `rt.after_node` | `fn(result) -> result` (sync or async) | `middleware=` or `model_middleware=` | No — skipped on exception |

- All five accept optional keyword-only `name=` and work bare or called: `@rt.before_llm`, `@rt.after_node(name="print_after")`.
- `wrap_node`/`wrap_llm` require `async def` (`TypeError` otherwise). `before_llm`/`after_llm`/`after_node` accept sync or async.
- `middleware=` wraps the whole node call (an agent's full tool-calling loop, including every tool node it invokes). `model_middleware=` wraps one raw LLM call inside that loop.
- Attach at creation — `rt.agent_node(..., middleware=[...], model_middleware=[...])` — or after the fact without mutating the original — `rt.couple(node, middleware=[...], model_middleware=[...])`.
- List order = wrapping order: `middleware=[A, B, C]` → `A` wraps `B` wraps `C` wraps the node. `rt.couple`-ing more onto an already-middlewared node adds the new ones innermost; existing middleware stays outermost.

---

## Best practices

### 1. Exception handling & retries
- `before_llm`, `after_llm`, `after_node` **only run on success** — an exception skips them entirely. If you need to react to failure (cleanup, translation, fallback), use `wrap_node`/`wrap_llm` and put your own `try`/`except` around `await call(...)`.
- **Where you put a retry changes what it re-executes:**
  - `model_middleware=` retry only re-issues the raw LLM call — safe by default, no side effects beyond the model provider request.
  - `middleware=` retry on an agent re-runs the **entire node**, including every tool call that already succeeded in that attempt. Only retry at this slot if the tools involved are safe to re-run (idempotent, or guarded by an idempotency key) — otherwise a transient failure after a non-idempotent tool call (e.g. "send email", "charge card") causes it to fire twice.
  - Default to retrying in `model_middleware=` for provider flakiness (rate limits, timeouts). Reach for `middleware=` retry only when you've confirmed the tools are safe to repeat.
- Prefer `railtracks.prebuilt.middleware.Retry(max_tries=..., approach=..., retry_on=...)` over hand-rolling — it raises once attempts are exhausted rather than swallowing the failure, and lets you scope `retry_on` to specific exception types instead of catching everything.
- Don't swallow exceptions silently inside a `wrap_node`/`wrap_llm` middleware (`except Exception: return default`) — that hides the failure from callers and from anything else in the chain. If you must return a fallback, do it deliberately (log it, tag it in the result) rather than as an unannounced side effect.

### 2. Middleware vs. guardrails
- `rt.input_guard` / `rt.output_guard` are middleware under the hood (`BaseGuardrail` extends `Middleware`), specialized for one thing: "should this content pass?" The guard function receives an `LLMGuardrailEvent` and returns a `GuardrailDecision` (`allow` / `block` / `transform`).
- Use a guard, not hand-rolled middleware, whenever the logic is a content-policy decision (PII/secrets detection, profanity, jailbreak checks, redaction). You get for free: structured `GuardrailTrace` records (`rail_name`, `phase`, `action`, `reason`), `fail_open=` to decide whether a guard's own bug blocks or passes traffic, and consistent block semantics other tooling can rely on.
- Use plain middleware for everything that isn't a pass/block decision on content: retries, timing, logging, context injection, auth/telemetry.

### 3. Ordering & composition
- Two different things happen depending on middleware shape — know which one you're ordering:
  - **Input-transforming middleware** (`before_llm`-style: mutates `message_history`/`schema`/`tools` before calling onward) — earlier entries in the list run first and hand their result to later entries. Put transformations before validations: `model_middleware=[ContextInjection(), my_guard]` so the guard sees the filled-in prompt, not the raw template.
  - **Span-wrapping middleware** (retry, timing, logging that brackets a whole call) — the outermost entry sees the aggregate outcome; the innermost is what actually gets re-invoked on each attempt. `middleware=[Retry(3), log_after]` → the log fires once per retry attempt (it's inside the retry). `middleware=[log_after, Retry(3)]` → the log fires once, for the final outcome only (it's outside the retry). Pick based on whether you want per-attempt or per-call visibility.
- When `rt.couple`-ing middleware onto a node that already has some, the new list is innermost — it can't run "before" existing outer middleware like auth checks.

### 4. Naming & observability
- `name=` sets `Middleware.name`, which is tracked as part of observability — the same way guardrails write their `name` into every `GuardrailTrace.rail_name`. Give your middleware a real `name=` so it's identifiable in traces/logs instead of falling back to the wrapper function's `__name__`.
- Set `name=` when the same wrapper function is reused in more than one slot (e.g. one generic `retry_node` attached to several agents) and you need to tell instances apart.
- Keep one concern per middleware function. A function that both logs and mutates the prompt makes the ordering question in §3 ambiguous — split it into two so each one has one clear rule for where it belongs in the list.

---

## Patterns

### Retry: prebuilt vs. hand-rolled, and where to put it
```python
import railtracks as rt
from railtracks.prebuilt import middleware

Agent = rt.agent_node(
    "Agent",
    tool_nodes=[send_email],  # has a side effect — don't retry the whole node
    llm=rt.llm.OpenAILLM(model_name="gpt-4o"),
    model_middleware=[middleware.Retry(max_tries=3)],  # retries only the raw LLM call
)
```

### Guardrail vs. plain middleware for the same-shaped problem
```python
import railtracks as rt

# Content-policy decision -> guardrail, not middleware
@rt.input_guard
def block_secrets(event: rt.guardrails.LLMGuardrailEvent) -> rt.guardrails.GuardrailDecision:
    if any("SECRET" in m.content for m in event.messages if isinstance(m.content, str)):
        return rt.guardrails.GuardrailDecision.block(reason="secret leaked")
    return rt.guardrails.GuardrailDecision.allow()

# Not a policy decision -> plain middleware
@rt.before_llm
def log_prompt(message_history, schema, tools):
    print(message_history)
    return message_history, schema, tools
```

### Ordering a retry against a logger to control per-attempt vs. per-call visibility
```python
import railtracks as rt

@rt.after_node(name="print_after")
async def log_result(result):
    print("Finished:", result)
    return result

retry = rt.prebuilt.middleware.Retry(max_tries=3)

PerAttemptLogging = rt.couple(Agent, middleware=[retry, log_result])   # logs every attempt
PerCallLogging = rt.couple(Agent, middleware=[log_result, retry])     # logs only the final outcome
```

### Attaching middleware after the node already exists
```python
import railtracks as rt

Adjusted = rt.couple(
    Agent,
    middleware=[log_result],
    model_middleware=[log_prompt],
)
```

---

## Things to Avoid
- Don't retry at `middleware=` on an agent with non-idempotent tools — it re-runs every tool call in that attempt, not just the failed step.
- Don't hand-roll a content allow/block check as plain middleware — use `input_guard`/`output_guard` so it shows up in `GuardrailTrace` like the rest of your rails.
- Don't write a plain `def` for `wrap_node`/`wrap_llm` — it must be `async def`.
- Don't expect `after_llm`/`after_node` to run on failure — they're success-only; use `wrap_llm`/`wrap_node` if you need failure-aware logic.
- Don't assume `name=` changes what shows up in railtracks' own traces — it doesn't (yet), outside of guardrails.
