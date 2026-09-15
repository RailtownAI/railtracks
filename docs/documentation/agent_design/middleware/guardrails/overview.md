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
agent = rt.agent_node(..., model_middleware=[my_input_guard, my_output_guard])
```

See [Attaching Middleware](../overview.md#attaching-middleware) for creation-time vs. after-creation attachment and ordering.

## Prebuilt Guards

We ship a set of prebuilt guardrails for common use cases including blocked text, length limits, and PII redaction. See the [prebuilt catalog](../prebuilt/overview.md#guardrails).

## Custom Guards

A guard evaluates a `LLMGuardrailEvent` and returns a `GuardrailDecision`: `allow()`, `block(...)`, or a `transform_*(...)`. There are two ways to write one.

### The decorator API

The quickest way is `@rt.input_guard` / `@rt.output_guard`: decorate a plain function that takes the event and returns a decision. The decorator turns it into a ready-to-attach guard.

```python
--8<-- "docs/scripts/custom_guardrails.py:decorator_imports"
```

```python
--8<-- "docs/scripts/custom_guardrails.py:decorator_input"
```

Output guards inspect `event.output_message` and can rewrite the reply with `transform_output(...)`. They fire only on the final reply (intermediate tool-call turns pass through). The parameterized form takes `name=` (for traces) and `fail_open=` (let the call through if the guard raises):

```python
--8<-- "docs/scripts/custom_guardrails.py:decorator_output"
```

Attach them like any model middleware:

```python
--8<-- "docs/scripts/custom_guardrails.py:decorator_attach"
```

### Async guards

A guard may be a regular `def` or an `async def`. An async rail is awaited while it is evaluated, so it can `await` anything, including `rt.call` into another agent. That is how you build an LLM-judge rail, where the decision is delegated to a second agent:

```python
--8<-- "docs/scripts/custom_guardrails.py:decorator_async"
```

Give the judge an `output_schema` rather than parsing its prose: the rail then branches on a typed field instead of substring-matching a reply that can be reworded at any time, and the judge's own `reason` carries straight into the block.

The same holds when subclassing: define `async def __call__(self, event)` and everything downstream of the decision is identical.

!!! warning "An async rail runs once per model round-trip"
    Guards are model middleware, so a rail fires on every model call, not once per agent call. On a tool-calling agent that means once per iteration of the tool loop: an input rail on an agent that takes three tool turns fires four times, each seeing a longer history. That is free for a regex check but not for a rail that makes its own LLM call. Output rails are exempt from intermediate tool-call turns and fire only on the final reply.

    If a rail only needs to screen the user's original request, consider attaching it as node-level middleware ([`wrap_node`](../overview.md)) instead, which runs once per agent call.

### Subclassing

For a reusable, configurable rail, subclass `InputGuard` or `OutputGuard` and implement `__call__(self, event) -> GuardrailDecision`. This is how the [prebuilt guards](../prebuilt/overview.md#guardrails) are built.

```python
--8<-- "docs/scripts/custom_guardrails.py:subclass_imports"
```

```python
--8<-- "docs/scripts/custom_guardrails.py:subclass"
```

!!! tip "Testing a guard in isolation"
    Both bases provide `decide(value)`, which builds the event for you from a `str`, `Message`, or `MessageHistory` and returns the `GuardrailDecision`, handy for unit tests without running a model. For an async guard use `await guard.adecide(value)`; `decide()` raises `TypeError` on one, since it would otherwise hand back an un-awaited coroutine.

To publish a guard for others to reuse, see [Contributing a Guardrail](contributions.md).

The next section, [Quickstart](quickstart.md), walks through attaching a guard to an agent and seeing a request pass or block in practice.
