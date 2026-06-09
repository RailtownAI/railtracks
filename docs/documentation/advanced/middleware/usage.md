# Middleware: Wrappers & Gateways

Middleware lets you add behaviour *around* a node's execution — retries, logging,
input/output transforms, redaction, guardrails — without changing the node's own logic.
Railtracks wraps **every** entry point (function nodes, agents, tools, and the raw LLM
model call) with the same two primitives, so one mental model covers them all.

- **[`Wrapper`](#wrapper-execution-control)** — *execution control*: it receives the
  inner call and decides whether / how / how many times to run it.
- **[`Gateway`](#gateway-data-transforms)** — *data transform*: it reshapes the input
  before the call, or the output after it.

You group them with [`MiddlewareSet`](#grouping-with-middlewareset) and attach them to a
node via the [`middleware`](#attaching-middleware) parameter (and, for agents, the
[`model_middleware`](#agents-two-attach-sites) parameter).

!!! tip "See also"
    - Quick definitions: [Middleware glossary](../../../tutorials/concepts/glossary/middleware.md)
    - Architecture & design: [Middleware Internals](internals.md)
    - Higher-level guardrails: [Guardrails](../guardrails/overview.md)

---

## `Wrapper` — execution control

A wrapper is an **async** function whose first argument is `call`, the inner
(already-wrapped) callable. Because the wrapper *owns* the call, it can retry it, time
it, fall back to an alternative, or skip it entirely.

```python
import railtracks as rt

@rt.wrapper
async def retry(call, *args, **kwargs):
    """Retry the inner call up to 3 times."""
    last = None
    for attempt in range(3):
        try:
            return await call(*args, **kwargs)
        except Exception as e:
            last = e
    raise last

@rt.wrapper
async def timed(call, *args, **kwargs):
    import time
    start = time.perf_counter()
    result = await call(*args, **kwargs)
    print(f"[timed] {(time.perf_counter() - start) * 1000:.1f} ms")
    return result
```

A wrapper can **short-circuit** by simply not calling `call`:

```python
@rt.wrapper
async def cached(call, *args, **kwargs):
    key = (args, tuple(sorted(kwargs.items())))
    if key in _CACHE:
        return _CACHE[key]          # inner call never runs
    result = await call(*args, **kwargs)
    _CACHE[key] = result
    return result
```

!!! warning "Wrappers must be `async`"
    A wrapper has to `await` the inner call, which a plain `def` cannot do. A sync
    function passed to `@rt.wrapper` raises `TypeError`. (Gateways, below, may be sync.)

---

## `Gateway` — data transforms

A gateway is authored with `@rt.gateway` and may be **`async` or a plain `def`** (a sync
gateway runs inline). It carries **no direction** — *where you place it* decides its role:

- in `gateway_entry` it transforms the **input** before the call;
- in `gateway_exit` it transforms the **output** after the call.

### Entry gateways

An entry gateway receives the call's `(*args, **kwargs)` and returns the *new* arguments.
The return value is interpreted as:

| Return | Meaning |
|---|---|
| `None` | check-only — pass the call through unchanged |
| a `tuple` | the new **positional** args, e.g. `return (text,)` |
| a `dict` | the new **keyword** args, e.g. `return {"city": city}` |
| a `(tuple, dict)` pair | both positional and keyword args |
| `rt.gateway.args(*a, **k)` | both, stated explicitly |

```python
@rt.gateway
async def normalize(text: str):
    return (text.strip().lower(),)          # tuple -> positional args only

@rt.gateway
async def route(city: str):
    return {"city": city, "units": "metric"}  # dict -> keyword args only

@rt.gateway
async def reorder(a, b):
    return rt.gateway.args(b, a, flag=True)  # both -> ((b, a), {"flag": True})
```

!!! danger "A bare value raises `TypeError`"
    There is **no single-value shorthand**. Returning a lone string/number/object
    raises `TypeError`, so a returned `dict` is never silently unpacked as one
    positional arg. Wrap a single positional value explicitly: `return (x,)` or
    `return rt.gateway.args(x)`.

!!! note "`(tuple, dict)` vs a plain tuple"
    A 2-element tuple whose first item is a `tuple` and second is a `dict` is read as the
    full `(args, kwargs)` form. Any *other* tuple is positional args. If you genuinely
    need two positional args shaped like `(some_tuple, some_dict)`, use
    `rt.gateway.args(some_tuple, some_dict)` to remove the ambiguity.

### Exit gateways

An exit gateway receives the single `result` and returns the new one. Returning `None`
keeps the original result unchanged.

```python
@rt.gateway
async def add_banner(result: str):
    return f">>> {result} <<<"

@rt.gateway
async def audit(result):
    log.info("produced %r", result)        # returns None -> result unchanged
```

### Check-only gateways = guardrails

A gateway doesn't have to transform. An entry gateway can **validate and raise** to block
the call; if the input is fine it returns nothing. That is exactly a guardrail:

```python
@rt.gateway
async def no_secrets(text: str):
    if "password" in text.lower():
        raise ValueError("blocked: input mentions a secret")
    # returns None -> the call proceeds unchanged
```

For richer, ready-made guardrails (PII redaction, length/content checks) see
[Guardrails](../guardrails/overview.md).

---

## Grouping with `MiddlewareSet`

A `MiddlewareSet` is the ordered bundle attached to one site. It has four bands:

```python
rt.MiddlewareSet(
    outer_wrappers=[retry],       # wrappers outside the gateways
    gateway_entry=[normalize],    # transform input (before the core)
    gateway_exit=[add_banner],    # transform output (after the core)
    inner_wrappers=[cached],      # wrappers closest to the core
)
```

They compose as two wrapper layers sandwiching a gateway band:

```
outer_wrappers
└── gateway_entry              (transform input)
    └── inner_wrappers
        └── core               (node / function / model call)
    └── (unwind inner_wrappers)
└── gateway_exit               (transform output)
└── (unwind outer_wrappers)
```

So a single call flows: `outer-in → entry gateways → inner-in → CORE → inner-out →
exit gateways → outer-out`. Wrappers nest; gateways bracket the core from the middle.

### Bare lists

Anywhere a `MiddlewareSet` is accepted you can pass a **bare list** instead. It is
coerced: `Wrapper` items go to `outer_wrappers`, `Gateway` items go to `gateway_entry`
(use the explicit constructor for exit gateways or inner wrappers).

```python
middleware=[retry, no_secrets]    # retry -> outer_wrappers, no_secrets -> gateway_entry
```

### The decorator is optional in explicit slots

Inside an explicit `MiddlewareSet` slot the role is already known, so the
`@rt.wrapper` / `@rt.gateway` decorator is **optional** — a raw function works:

```python
async def add_marker(text):      # raw async function, no @rt.gateway
    return (f"[{text}]",)

def shout(result):               # raw *sync* function (gateways may be sync)
    return result.upper()

ms = rt.MiddlewareSet(gateway_entry=[add_marker], gateway_exit=[shout])
```

The decorator is only *required* for a bare list, where wrapper-vs-gateway would
otherwise be ambiguous. Putting a `Gateway` in a wrapper slot (or vice-versa) raises a
clear `TypeError`.

---

## Attaching middleware

### Function nodes

`rt.function_node` takes a `middleware` parameter — a `MiddlewareSet` or a bare list —
applied at the node boundary (its call args → its output):

```python
echo = rt.function_node(
    lambda text: f"echo: {text}",
    name="echo",
    middleware=rt.MiddlewareSet(gateway_entry=[normalize], gateway_exit=[add_banner]),
)
```

`function_node` also works as a **parametrized decorator**:

```python
@rt.function_node(middleware=[no_secrets])
async def lookup(user_id: str):
    ...
```

Because a tool *is* a node, middleware attached this way also runs when the function is
called as a tool by an agent.

### Agents: two attach sites

An LLM agent is not a single model call — its `invoke` runs a **tool-calling loop** that
may call the model several times. So agents expose **two** attach sites:

| Parameter | Wraps | Runs |
|---|---|---|
| `middleware` | the whole agent run (`user_input → Response`) | once per agent call |
| `model_middleware` | each **raw model call** (`messages, schema, tools → Response`) | once per model round-trip, inside the loop |

```python
assistant = rt.agent_node(
    name="Mentor",
    llm=rt.llm.OpenAILLM("gpt-4o-mini"),
    system_message="Answer in one sentence.",
    middleware=[no_secrets],                                   # node boundary
    model_middleware=rt.MiddlewareSet(gateway_entry=[scrub]),  # each model call
)
```

Use `middleware` for things that act on the user input / final answer; use
`model_middleware` for things that must see every intermediate model exchange (per-call
retries, message redaction, logging each round-trip). `function_node` has only
`middleware`, since a function node makes no model call.

!!! info "Cardinality matters"
    A `retry` wrapper on `middleware` re-runs the *entire* agent (all tool calls). The
    same wrapper on `model_middleware` retries just *one* model round-trip.

---

## End-to-end example

Scrub secrets out of the user input, restore them in the answer, and retry the whole run:

```python
import re
import railtracks as rt

@rt.wrapper
async def retry(call, *args, **kwargs):
    for attempt in range(3):
        try:
            return await call(*args, **kwargs)
        except Exception:
            if attempt == 2:
                raise

@rt.gateway
async def hide_secrets(text: str):
    found = re.findall(r"\b[A-Za-z0-9]{10,}\b", text)
    rt.context.put("secrets", found)
    return (re.sub(r"\b[A-Za-z0-9]{10,}\b", "[SECRET]", text),)   # tuple -> positional

@rt.gateway
async def restore_secrets(result):
    text = result.content if hasattr(result, "content") else result
    for s in rt.context.get("secrets") or []:
        text = text.replace("[SECRET]", s, 1)
    return text

assistant = rt.agent_node(
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="Echo [SECRET] tokens back verbatim.",
    middleware=rt.MiddlewareSet(
        outer_wrappers=[retry],
        gateway_entry=[hide_secrets],
        gateway_exit=[restore_secrets],
    ),
)
```

---

## Cheat sheet

- **`@rt.wrapper`** — async only; `(call, *args, **kwargs)`; `await call(...)`; retry /
  time / fall back / short-circuit.
- **`@rt.gateway`** — async or sync; direction set by slot.
    - entry returns: `None` (pass through) · `tuple` (args) · `dict` (kwargs) ·
      `(tuple, dict)` (both) · `rt.gateway.args(*a, **k)`; a bare value raises.
    - exit returns the new result, or `None` to keep the original. Raise to act as a
      guardrail.
- **`rt.MiddlewareSet(outer_wrappers, gateway_entry, gateway_exit, inner_wrappers)`** —
  or a bare list (wrappers → outer, gateways → entry). Decorator optional in slots.
- **Attach** with `middleware` (every node) and, for agents, `model_middleware` (each
  raw model call).
- Your list is never mutated; framework middleware (e.g. context injection) lives in
  separate internal layers — see [Internals](internals.md).
