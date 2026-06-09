# Middleware Internals

A developer-facing tour of how the middleware system is built. For how to *use* it, see
the [Usage Guide](usage.md). This page is for contributors and anyone registering
framework-level middleware.

## Module layout

Everything lives in `railtracks/middleware/`:

- `primitives.py` — the `Wrapper` and `Gateway` classes, their `@wrapper` / `@gateway`
  decorators, the `gateway.args(...)` helper, and the `_GatewayArgs` tag.
- `set.py` — `MiddlewareSet` (the container + the `run` execution engine), the internal
  `_LayeredList`, and the coercion/validation helpers.
- `__init__.py` — re-exports (`Wrapper`, `wrapper`, `Gateway`, `gateway`, `MiddlewareSet`).

There is **one engine** (`MiddlewareSet.run`) used at every attach site, so wrappers and
gateways behave identically whether they wrap a function node, an agent, a tool, or a raw
model call.

## The three-layer list

Each band is not a plain list but a `_LayeredList`, which holds three ordered layers:

```
[sys_before]  →  [user]  →  [sys_after]
```

- `sys_before` — framework middleware that must run *before* user middleware.
- `user` — exactly what the caller passed (copied in on construction, never mutated).
- `sys_after` — framework middleware that runs *after* user middleware.

`ordered()` flattens them to `sys_before + user + sys_after`. The public iteration
interface (`__iter__`, `__len__`, the `MiddlewareSet` properties) exposes the **user**
layer only, so registering system middleware is invisible to user-facing views. This is
how the framework injects behaviour (see [context injection](#context-injection)) without
ever touching the user's list.

## `MiddlewareSet`

Four bands, each a `_LayeredList`:

```python
self._outer   # _LayeredList[Wrapper]
self._entry   # _LayeredList[Gateway]
self._exit    # _LayeredList[Gateway]
self._inner   # _LayeredList[Wrapper]
```

### Construction & coercion

- The constructor coerces each slot: a raw async function (or, for gateways, a sync
  function) is auto-wrapped into a `Wrapper` / `Gateway`; an already-built primitive of
  the *wrong* type for the slot raises `TypeError`. This is why the decorator is optional
  in explicit slots but the cross-type mistake is still caught.
- `MiddlewareSet.coerce(value)` normalises user input: `None` → empty set; a
  `MiddlewareSet` → a fresh copy; a list/tuple → `Wrapper`s to `outer_wrappers`,
  `Gateway`s to `gateway_entry` (a bare list can't express exit gateways or inner
  wrappers, and raw functions are ambiguous there, so the decorator is required).
- `_fresh_copy()` / `copy_user_only()` produce a copy carrying only the **user** layers,
  with system layers reset — so a `MiddlewareSet` reused across nodes gives each site its
  own independent system layers and the caller's object is never mutated.

### The execution engine

`run(core, args, kwargs)` composes the onion and awaits it:

```python
inner = core
for w in reversed(self._inner.ordered()):
    inner = w.wrap(inner)

async def gated(*a, **k):
    for g in self._entry.ordered():
        a, k = await g.apply_entry(*a, **k)
    result = await inner(*a, **k)
    for g in self._exit.ordered():
        result = await g.apply_exit(result)
    return result

outer = gated
for w in reversed(self._outer.ordered()):
    outer = w.wrap(outer)

return await outer(*args, **kwargs)
```

Wrappers are applied in **reversed** order so the first wrapper in the list ends up
outermost. Entry/exit gateways are **separate lists** driven in `gated`, which is why the
final order is `outer → entry → inner → core → exit (unwind) → outer (unwind)`.

## Primitives

### `Wrapper`

`Wrapper.__init__` calls `_require_async` — a wrapper must be a coroutine function,
because `wrap` produces:

```python
async def wrapped(*args, **kwargs):
    return await self._fn(inner, *args, **kwargs)
```

The wrapper is handed `inner` (the already-composed next layer) and is responsible for
awaiting it. A sync function cannot `await`, so it is rejected at construction time.

### `Gateway`

`Gateway.__init__` only requires a callable and records `self._is_async`. `_invoke`
bridges sync/async:

```python
async def _invoke(self, *args, **kwargs):
    if self._is_async:
        return await self._fn(*args, **kwargs)
    return self._fn(*args, **kwargs)     # sync gateway: run inline
```

Sync gateways run **inline** (not in a thread) deliberately, so a sync gateway's
`rt.context` writes stay on the current context.

`apply_entry` implements the return contract, in this order: `None` → pass through;
`_GatewayArgs` → its `(args, kwargs)`; a `(tuple, dict)` 2-tuple → full form; a `tuple` →
positional-only; a `dict` → keyword-only; anything else → `TypeError`. `apply_exit`
returns the new result, or the original when the gateway returns `None`.

`gateway.args(*a, **k)` returns a `_GatewayArgs` tag carrying both; it is the only
unambiguous way to state positional **and** keyword args at once, and the escape hatch
for the rare "single positional arg that looks like `(tuple, dict)`" case.

## Attach-site integration

### Node middleware

The base `Node` carries a class-level `frozen_middleware: MiddlewareSet` default. Each
instance takes a fresh copy in `__init__` (`self.middleware = self.frozen_middleware
._fresh_copy()`), and runs through it via:

```python
async def wrapped_invoke(self, *args, **kwargs):
    return await self.middleware.run(self.invoke, args, kwargs)
```

`wrapped_invoke` is what the executor actually calls, so **every** node type goes through
its node-level middleware exactly once per call. `NodeBuilder` sets `frozen_middleware`
from the `middleware=` argument via `MiddlewareSet.coerce`.

### Model middleware

`model_middleware` is owned by `ModelInvoker`, which wraps the *raw* model call:

```python
async def _core_llm_call(messages, schema, tools):
    ...  # model.chat / structured / chat_with_tools
return await self._middleware.run(_core_llm_call, (messages, schema, tools), {})
```

`ModelInvoker.invoke` is called inside the agent's tool-calling loop, so model middleware
runs **once per model round-trip** — a different cardinality and a different core
signature (`(messages, schema, tools) → Response`) than node middleware. Function nodes
have no `ModelInvoker`, hence no `model_middleware`.

### Context injection

The one framework middleware wired today: when an LLM node is built with
`context_injection=True`, `NodeBuilder` registers `context_injection_gateway` as a
**system entry gateway** on the model-level set:

```python
model_invoker.register_sys_gateway_entry(context_injection_gateway)
```

It lands in the model band's `sys_before` layer, runs before any user entry gateway on
every model call, fills `{placeholder}` slots from `rt.context`, and is invisible to the
public `gateway_entry` view.

## System-registration hooks

`MiddlewareSet` exposes four idempotent hooks for framework code (never the user layer):

- `register_sys_gateway_entry(gw)` → entry `sys_before`
- `register_sys_gateway_exit(gw)` → exit `sys_after`
- `register_sys_outer_wrapper(w)` → outer `sys_before`
- `register_sys_inner_wrapper(w)` → inner `sys_after`

Context injection is the only one wired today; the others exist for future framework
middleware (tracing, cost accounting, etc.).

## Design rationale

- **Wrappers are async-only.** They must `await` the inner call on the event loop;
  running a sync wrapper off-loop (e.g. in a thread) would lose the run's context, so it
  is rejected rather than silently bridged.
- **Sync gateways run inline.** A gateway never awaits the inner call, so a sync gateway
  is a cheap inline transform — and inline keeps `rt.context` writes on the live context.
- **No single-value shorthand for entry returns.** Every accepted entry return is a
  structured container (`tuple`/`dict`/pair/`gateway.args`/`None`), so a returned `dict`
  is unambiguously keyword args and is never silently unpacked as one positional arg.
- **Direction-less gateways.** The same `Gateway` object works in entry or exit slots;
  the slot picks `apply_entry` vs `apply_exit`. This keeps the primitive small and avoids
  two near-identical decorators.
- **User lists are never mutated.** Construction copies the user layer; system middleware
  lives in separate layers; reuse takes a fresh copy. A `MiddlewareSet` is safe to share
  across many nodes.

See the [Usage Guide](usage.md) for the user-facing API.
