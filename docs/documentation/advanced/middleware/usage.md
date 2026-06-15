# Middleware: Wrappers & Gateways

Middleware adds behaviour *around* a node's execution — retries, logging, input/output
transforms, redaction, guardrails — without changing the node's own logic. Every entry
point (function nodes, agents, tools, and the raw LLM model call) uses the same two
primitives, so one mental model covers them all:

- **`Wrapper`** — *execution control*: receives the inner call and decides whether / how /
  how many times to run it.
- **`Gateway`** — *data transform*: reshapes the input before the call, or the output after it.

Group them with `MiddlewareSet` and attach them via the `middleware` parameter (and, for
agents, `model_middleware`).

!!! tip "See also"
    - Quick definitions: [Middleware glossary](../../../tutorials/concepts/glossary/middleware.md)
    - Architecture & design: [Middleware Internals](internals.md)
    - Higher-level guardrails: [Guardrails](../guardrails/overview.md)

---

## `Wrapper` — execution control

A wrapper is an **async** function whose first argument is `call`, the inner
(already-wrapped) callable. Because the wrapper *owns* the call, it can retry it, time it,
fall back, or skip it entirely.

```python
--8<-- "docs/scripts/middleware.py:wrappers"
```

A wrapper can **short-circuit** by simply not calling `call`:

```python
--8<-- "docs/scripts/middleware.py:wrapper_cached"
```

!!! warning "Wrappers must be `async`"
    A wrapper has to `await` the inner call, which a plain `def` cannot do. A sync function
    passed to `@rt.wrapper` raises `TypeError`. (Gateways, below, may be sync.)

---

## `Gateway` — data transforms

A gateway is authored with `@rt.gateway` and may be **`async` or a plain `def`** (a sync
gateway runs inline). It carries **no direction** — *where you place it* decides its role:
`gateway_entry` transforms the **input** before the call; `gateway_exit` transforms the
**output** after it.

### Entry gateways

An entry gateway receives the call's `(*args, **kwargs)` and returns the *new* arguments:

| Return | Meaning |
|---|---|
| `None` | check-only — pass the call through unchanged |
| a `tuple` | the new **positional** args, e.g. `return (text,)` |
| a `dict` | the new **keyword** args, e.g. `return {"city": city}` |
| a `(tuple, dict)` pair | both positional and keyword args |
| `rt.gateway.args(*a, **k)` | both, stated explicitly |

```python
--8<-- "docs/scripts/middleware.py:gateway_entry"
```

!!! danger "A bare value raises `TypeError`"
    There is **no single-value shorthand**, so a returned `dict` is never silently unpacked
    as one positional arg. Wrap a single positional value explicitly: `return (x,)` or
    `return rt.gateway.args(x)`. A 2-tuple of `(tuple, dict)` is read as the full
    `(args, kwargs)` form — use `rt.gateway.args(...)` if you genuinely need two positional
    args shaped that way.

### Exit gateways

An exit gateway receives the single `result` and returns the new one. Returning `None`
keeps the original unchanged.

```python
--8<-- "docs/scripts/middleware.py:gateway_exit"
```

### Check-only gateways = guardrails

A gateway doesn't have to transform. An entry gateway can **validate and raise** to block
the call, returning nothing when the input is fine — that is exactly a guardrail:

```python
--8<-- "docs/scripts/middleware.py:gateway_guardrail"
```

For ready-made guardrails (PII redaction, length/content checks) see
[Guardrails](../guardrails/overview.md).

### Calling a gateway directly

A `Gateway` is **directly callable**, passing straight through to the function you wrote —
handy when the gateway is a generic helper you also want to call normally:

```python
--8<-- "docs/scripts/middleware.py:gateway_direct_call"
```

!!! warning "Direct call is the *raw* function, not the slot behaviour"
    Calling `gateway(...)` runs the underlying function as-is; it does **not** apply the
    entry/exit interpretation. Use `gateway.apply_entry(...)` / `gateway.apply_exit(...)`
    to see what the engine does. If the gateway is `async`, calling it returns a
    **coroutine** you must `await`.

---

## Grouping with `MiddlewareSet`

A `MiddlewareSet` is the ordered bundle attached to one site. It has four bands:

```python
--8<-- "docs/scripts/middleware.py:middlewareset_bands"
```

They compose as two wrapper layers sandwiching a gateway band:

```
wrappers
└── gateway_entry              (transform input)
    └── inner_wrappers
        └── core               (node / function / model call)
    └── (unwind inner_wrappers)
└── gateway_exit               (transform output)
└── (unwind wrappers)
```

A single call flows `wrappers-in → entry gateways → inner-in → CORE → inner-out → exit
gateways → wrappers-out`. Wrappers nest; gateways bracket the core from the middle.

### Bare lists

Anywhere a `MiddlewareSet` is accepted you can pass a **bare list** instead. It is coerced:
`Wrapper` items go to `wrappers`, `Gateway` items go to `gateway_entry` (use the explicit
constructor for exit gateways or inner wrappers).

```python
--8<-- "docs/scripts/middleware.py:bare_list"
```

### The decorator is optional in explicit slots

Inside an explicit `MiddlewareSet` slot the role is already known, so the `@rt.wrapper` /
`@rt.gateway` decorator is **optional** — a raw function works:

```python
--8<-- "docs/scripts/middleware.py:raw_in_slots"
```

The decorator is only *required* for a bare list, where wrapper-vs-gateway would otherwise
be ambiguous. Putting a `Gateway` in a wrapper slot (or vice-versa) raises a clear
`TypeError`.

---

## Attaching middleware

### Function nodes

`rt.function_node` takes a `middleware` parameter — a `MiddlewareSet` or a bare list —
applied at the node boundary (its call args → its output):

```python
--8<-- "docs/scripts/middleware.py:attach_function_node"
```

It also works as a **parametrized decorator**:

```python
--8<-- "docs/scripts/middleware.py:attach_function_decorator"
```

Because a tool *is* a node, middleware attached this way also runs when the function is
called as a tool by an agent.

### Agents: two attach sites

An LLM agent's `invoke` runs a **tool-calling loop** that may call the model several times,
so agents expose **two** attach sites:

| Parameter | Wraps | Runs |
|---|---|---|
| `middleware` | the whole agent run (`user_input → Response`) | once per agent call |
| `model_middleware` | each **raw model call** (`messages, schema, tools → Response`) | once per model round-trip |

```python
--8<-- "docs/scripts/middleware.py:attach_agent"
```

Use `middleware` for things that act on the user input / final answer; use
`model_middleware` for things that must see every intermediate model exchange. A `retry`
on `middleware` re-runs the *entire* agent; the same wrapper on `model_middleware` retries
just *one* model round-trip. `function_node` has only `middleware`, since it makes no model
call.

---

## Choosing the model at runtime

`agent_node`'s `llm` parameter accepts either a model **or a no-arg factory**
(`ModelBase | Callable[[], ModelBase]`). A factory is resolved fresh on every model call,
so a built agent can pick its model at invocation time — from config, `rt.context`, or any
runtime signal — instead of binding one at build time:

```python
--8<-- "docs/scripts/middleware.py:model_source"
```

---

## End-to-end example

Scrub secrets out of the user input, restore them in the answer, and retry the whole run:

```python
--8<-- "docs/scripts/middleware.py:end_to_end"
```

---

## Cheat sheet

- **`@rt.wrapper`** — async only; `(call, *args, **kwargs)`; `await call(...)`; retry / time
  / fall back / short-circuit.
- **`@rt.gateway`** — async or sync; direction set by slot. Entry returns `None` / `tuple` /
  `dict` / `(tuple, dict)` / `rt.gateway.args(*a, **k)` (a bare value raises). Exit returns
  the new result, or `None` to keep the original; raise to act as a guardrail.
- **`rt.MiddlewareSet(wrappers, gateway_entry, gateway_exit, inner_wrappers)`** — or a bare
  list (wrappers → `wrappers`, gateways → `gateway_entry`). Decorator optional in slots.
- **Attach** with `middleware` (every node) and, for agents, `model_middleware` (each raw
  model call). `llm` also accepts a no-arg model factory.
- Your list is never mutated; framework middleware (e.g. context injection) lives in
  separate internal layers — see [Internals](internals.md).
