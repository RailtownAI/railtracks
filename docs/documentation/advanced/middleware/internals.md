# Middleware Internals

A developer-facing tour of how the middleware system is built. For how to *use* it, see
the [Usage Guide](usage.md). This page is for contributors and anyone registering
framework-level middleware. Code is referenced by source location rather than reproduced,
so it can't drift from the implementation.

## Module layout

Everything lives in `railtracks/middleware/`:

- `primitives.py` — the `Wrapper` and `Gate` classes, their `@wrapper` / `@gate`
  decorators, the `gate.args(...)` helper, and the `_GateArgs` tag.
- `set.py` — `MiddlewareChain` (the container + the `run` execution engine), the internal
  `_LayeredList`, and the coercion/validation helpers.
- `__init__.py` — re-exports (`Wrapper`, `wrapper`, `Gate`, `gate`, `MiddlewareChain`).

There is **one engine** (`MiddlewareChain.run`) used at every attach site, so wrappers and
gates behave identically whether they wrap a function node, an agent, a tool, or a raw
model call.

## The three-layer list

Each band is a `_LayeredList`, holding three ordered layers:

```
[sys_before]  →  [user]  →  [sys_after]
```

- `sys_before` — framework middleware that must run *before* user middleware.
- `user` — exactly what the caller passed (copied in on construction, never mutated).
- `sys_after` — framework middleware that runs *after* user middleware.

`ordered()` flattens them to `sys_before + user + sys_after`. The public iteration
interface (`__iter__`, `__len__`, the `MiddlewareChain` properties) exposes the **user**
layer only, so registering system middleware is invisible to user-facing views. This is
how the framework injects behaviour (see [context injection](#context-injection)) without
ever touching the user's list.

## `MiddlewareChain`

Four bands, each a `_LayeredList`: `self._outer` and `self._inner` hold `Wrapper`s,
`self._entry` and `self._exit` hold `Gate`s. The public band names are `wrappers`,
`entry_gate`, `exit_gate`, and `inner_wrappers`.

### Construction & coercion

- The constructor coerces each slot: a raw async function (or, for gates, a sync
  function) is auto-wrapped into a `Wrapper` / `Gate`; an already-built primitive of the
  *wrong* type for the slot raises `TypeError`. This is why the decorator is optional in
  explicit slots but the cross-type mistake is still caught.
- `MiddlewareChain.coerce(value)` normalises user input: `None` → empty set; a `MiddlewareChain`
  → a fresh copy; a list/tuple → `Wrapper`s to `wrappers`, `Gate`s to `entry_gate` (a
  bare list can't express exit gates or inner wrappers, and raw functions are ambiguous
  there, so the decorator is required).
- `_fresh_copy()` / `copy_user_only()` produce a copy carrying only the **user** layers,
  with system layers reset — so a `MiddlewareChain` reused across nodes gives each site its
  own independent system layers and the caller's object is never mutated.

### The execution engine

`MiddlewareChain.run(core, args, kwargs)` (in `set.py`) composes the onion and awaits it:

1. Wrap `core` with the **inner** wrappers, applied in **reversed** `ordered()` order so the
   first inner wrapper ends up closest to the core.
2. Build a `gated` callable that runs every **entry** gate (`apply_entry`), calls the
   inner stack, then runs every **exit** gate (`apply_exit`).
3. Wrap `gated` with the **outer** wrappers, again reversed so the first one ends up
   outermost.

Wrappers are reversed at composition so the first wrapper in each list is the outermost of
its layer; entry/exit gates are **separate lists** driven inside `gated`. The resulting
order is `wrappers → entry → inner → core → exit (unwind) → wrappers (unwind)`.

## Primitives

### `Wrapper`

`Wrapper.__init__` calls `_require_async` — a wrapper must be a coroutine function, because
`wrap(inner)` returns an `async` callable that `await`s `self._fn(inner, *args, **kwargs)`.
The wrapper is handed `inner` (the already-composed next layer) and is responsible for
awaiting it. A sync function cannot `await`, so it is rejected at construction time. `wrap`
is typed with a `ParamSpec`, so composing a wrapper preserves the wrapped callable's
signature.

### `Gate`

`Gate.__init__` only requires a callable and records `self._is_async`. `_invoke` bridges
sync/async: an async gate is awaited, a sync gate is run **inline** (not in a thread)
deliberately, so a sync gate's `rt.context` writes stay on the current context.

`apply_entry` implements the return contract, in this order: `None` → pass through;
`_GateArgs` → its `(args, kwargs)`; a `(tuple, dict)` 2-tuple → full form; a `tuple` →
positional-only; a `dict` → keyword-only; anything else → `TypeError`. `apply_exit` returns
the new result, or the original when the gate returns `None`.

`gate.args(*a, **k)` returns a `_GateArgs` tag carrying both; it is the only
unambiguous way to state positional **and** keyword args at once, and the escape hatch for
the rare "single positional arg that looks like `(tuple, dict)`" case.

`Gate.__call__` is a thin pass-through to `self._fn` — it preserves decorator
transparency (a `@gate`-decorated name stays usable as a plain function) and makes
generic gates easy to unit-test or reuse. It deliberately does **not** go through
`apply_entry` / `apply_exit`, so it returns the raw function result (a coroutine for an
async gate).

## Attach-site integration

### Node middleware

The base `Node` carries a class-level `frozen_middleware: MiddlewareChain` default. Each
instance takes a fresh copy in `__init__` (`self.middleware = self.frozen_middleware
._fresh_copy()`), and `wrapped_invoke` runs `invoke` through it
(`self.middleware.run(self.invoke, args, kwargs)`). `wrapped_invoke` is what the executor
calls, so **every** node type goes through its node-level middleware exactly once per call.
`NodeBuilder` sets `frozen_middleware` from the `middleware=` argument via
`MiddlewareChain.coerce`.

### Model middleware

`model_middleware` is owned by `ModelInvoker` (in `llm_helpers.py`), which runs the *raw*
model call (`model.chat` / `structured` / `chat_with_tools`) through its `MiddlewareChain`.
`ModelInvoker.invoke` is called inside the agent's tool-calling loop, so model middleware
runs **once per model round-trip** — a different cardinality and a different core signature
(`(messages, schema, tools) → Response`) than node middleware. Function nodes have no
`ModelInvoker`, hence no `model_middleware`.

`ModelInvoker` accepts a `ModelSource` — a `ModelBase` *or* a no-arg `Callable` returning
one — and resolves it on **every** `invoke`. A factory therefore lets a node swap its model
at invocation time (from config or `rt.context`) rather than binding one at build time.

### Context injection

The one framework middleware wired today: when an LLM node is built with
`context_injection=True`, `NodeBuilder` registers `context_injection_gate` as a
**system entry gate** on the model-level set
(`model_invoker.register_sys_entry_gate(context_injection_gate)`). It lands in the
model band's `sys_before` layer, runs before any user entry gate on every model call,
fills `{placeholder}` slots from `rt.context`, and is invisible to the public
`entry_gate` view.

## System-registration hooks

`MiddlewareChain` exposes four idempotent hooks for framework code (never the user layer):

- `register_sys_entry_gate(gw)` → entry `sys_before`
- `register_sys_exit_gate(gw)` → exit `sys_after`
- `register_sys_outer_wrapper(w)` → outer `sys_before`
- `register_sys_inner_wrapper(w)` → inner `sys_after`

Context injection is the only one wired today; the others exist for future framework
middleware (tracing, cost accounting, etc.).

## Design rationale

- **Wrappers are async-only.** They must `await` the inner call on the event loop; running a
  sync wrapper off-loop (e.g. in a thread) would lose the run's context, so it is rejected
  rather than silently bridged.
- **Sync gates run inline.** A gate never awaits the inner call, so a sync gate is a
  cheap inline transform — and inline keeps `rt.context` writes on the live context.
- **No single-value shorthand for entry returns.** Every accepted entry return is a
  structured container, so a returned `dict` is unambiguously keyword args and is never
  silently unpacked as one positional arg.
- **Direction-less gates.** The same `Gate` object works in entry or exit slots; the
  slot picks `apply_entry` vs `apply_exit`. This keeps the primitive small and avoids two
  near-identical decorators.
- **User lists are never mutated.** Construction copies the user layer; system middleware
  lives in separate layers; reuse takes a fresh copy. A `MiddlewareChain` is safe to share
  across many nodes.

See the [Usage Guide](usage.md) for the user-facing API.
