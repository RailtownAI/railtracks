# Guardrails Overview

Guardrails are a policy layer around agent execution. They inspect requests before they reach a model and responses before they are returned, letting you enforce rules for safety, reliability, and product behavior.

Guardrails aren't just about blocking unsafe content. They can also:

- Normalize inputs
- Redact sensitive data
- Enforce domain limits
- Shape outputs in a controlled, observable way

## Categories

Railtracks organizes guardrails into 2 categories:

- **LLM input guardrails**: inspect messages before the model call
- **LLM output guardrails**: inspect the model response before it is returned

## Usage

Guardrails are model middleware, so you attach them on the `model_middleware=` slot just like any other middleware:

```python
GuardedAgent = rt.agent_node(..., model_middleware=[my_input_guard, my_output_guard])
```

See [Attaching Middleware](https://docs.railtracks.org/documentation/agent_design/middleware/overview/#attaching-middleware) for creation-time vs. after-creation attachment and ordering.

## Prebuilt Guards

We ship a set of prebuilt guardrails for common use cases including blocked text, length limits, and PII redaction. See the [prebuilt catalog](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/overview/#guardrails).

## Custom Guards

A guard evaluates a `LLMGuardrailEvent` and returns a `GuardrailDecision`: `allow()`, `block(...)`, or a `transform_*(...)`. There are two ways to write one.

### The decorator API

The quickest way is `@rt.input_guard` / `@rt.output_guard`: decorate a plain function that takes the event and returns a decision. The decorator turns it into a ready-to-attach guard.

```python
from railtracks.guardrails import GuardrailDecision, LLMGuardrailEvent
```

```python
@rt.input_guard
def block_passwords(event: LLMGuardrailEvent) -> GuardrailDecision:
    """Block any input that asks for a password."""
    for message in event.messages:
        if isinstance(message.content, str) and "password" in message.content.lower():
            return GuardrailDecision.block(
                reason="Requests for passwords are not allowed.",
                user_facing_message="Ask for something else instead.",
            )
    return GuardrailDecision.allow()
```

Output guards inspect `event.output_message` and can rewrite the reply with `transform_output(...)`. They fire only on the final reply (intermediate tool-call turns pass through). The parameterized form takes `name=` (for traces) and `fail_open=` (let the call through if the guard raises):

```python
@rt.output_guard(name="no_sign_off", fail_open=True)
def strip_sign_off(event: LLMGuardrailEvent) -> GuardrailDecision:
    """Rewrite the final reply to drop a trailing sign-off line."""
    content = event.output_message.content if event.output_message else None
    if not isinstance(content, str) or "\nBest," not in content:
        return GuardrailDecision.allow()
    trimmed = content.split("\nBest,")[0].rstrip()
    return GuardrailDecision.transform_output(
        rt.llm.AssistantMessage(trimmed),
        reason="Removed sign-off.",
    )
```

Attach them like any model middleware:

```python
Agent = rt.agent_node(
    name="custom-guard-demo",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a concise assistant.",
    model_middleware=[block_passwords, strip_sign_off],
)
```

### Async guards

A guard may be a regular `def` or an `async def`. An async rail is awaited while it is evaluated, so it can `await` anything, including `rt.call` into another agent. That is how you build an LLM-judge rail, where the decision is delegated to a second agent:

```python
from pydantic import BaseModel


class SafetyReport(BaseModel):
    """The judge's verdict on one request."""

    safe_request: bool
    reason: str


Judge = rt.agent_node(
    name="safety-judge",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    output_schema=SafetyReport,
    system_message="You decide whether a user request is safe to answer.",
)


@rt.input_guard(name="llm_judge")
async def llm_judge(event: LLMGuardrailEvent) -> GuardrailDecision:
    """Delegate the decision to a second agent."""
    verdict = await rt.call(Judge, user_input=str(event.messages[-1].content))
    if not verdict.content.safe_request:
        return GuardrailDecision.block(
            reason=f"The judge flagged this request: {verdict.content.reason}",
            user_facing_message="I can't help with that.",
        )
    return GuardrailDecision.allow()
```

Give the judge an `output_schema` rather than parsing its prose: the rail then branches on a typed field instead of substring-matching a reply that can be reworded at any time, and the judge's own `reason` carries straight into the block.

The same holds when subclassing: define `async def __call__(self, event)` and everything downstream of the decision is identical.

An async rail runs once per model round-trip

Guards are model middleware, so a rail fires on every model call, not once per agent call. On a tool-calling agent that means once per iteration of the tool loop: an input rail on an agent that takes three tool turns fires four times, each seeing a longer history. That is free for a regex check but not for a rail that makes its own LLM call. Output rails are exempt from intermediate tool-call turns and fire only on the final reply.

If a rail only needs to screen the user's original request, consider attaching it as node-level middleware ([`wrap_node`](https://docs.railtracks.org/documentation/agent_design/middleware/overview/index.md)) instead, which runs once per agent call.

### Subclassing

For a reusable, configurable rail, subclass `InputGuard` or `OutputGuard` and implement `__call__(self, event) -> GuardrailDecision`. This is how the [prebuilt guards](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/overview/#guardrails) are built.

```python
from railtracks.guardrails import InputGuard
```

```python
class BlockKeywordGuard(InputGuard):
    """A reusable input guard that blocks a configurable keyword."""

    def __init__(self, keyword: str, *, name: str | None = None) -> None:
        super().__init__(name=name)
        self._keyword = keyword.lower()

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        for message in event.messages:
            if isinstance(message.content, str) and self._keyword in message.content.lower():
                return GuardrailDecision.block(
                    reason=f"Blocked keyword: {self._keyword}.",
                )
        return GuardrailDecision.allow()


guard = BlockKeywordGuard("password", name="BlockPassword")
```

Testing a guard in isolation

Both bases provide `decide(value)`, which builds the event for you from a `str`, `Message`, or `MessageHistory` and returns the `GuardrailDecision`, handy for unit tests without running a model. For an async guard use `await guard.adecide(value)`; `decide()` raises `TypeError` on one, since it would otherwise hand back an un-awaited coroutine.

To publish a guard for others to reuse, see [Contributing a Guardrail](https://docs.railtracks.org/documentation/agent_design/middleware/guardrails/contributions/index.md).

The next section, [Quickstart](https://docs.railtracks.org/documentation/agent_design/middleware/guardrails/quickstart/index.md), walks through attaching a guard to an agent and seeing a request pass or block in practice.
