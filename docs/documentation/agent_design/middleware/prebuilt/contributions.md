# Contributing a Prebuilt Middleware

Prebuilt middleware are the reusable add-ons that ship with Railtracks: things like [`Retry`](list/retry.md), [`ContextInjection`](list/context_injection.md), and the [prebuilt guards](overview.md#guardrails). If you have built a middleware that others would find useful, contributing it as a prebuilt one makes it a first-class, importable part of the library. This page walks through what a minimal middleware looks like, where it lives, and how to get it merged.

## A minimal middleware

A prebuilt middleware is just a `Middleware` subclass whose `__init__` captures its configuration and has an async method (`_middleware_fn` in this example) that wraps the inner `call`. Here is a complete, minimal example; a timeout that fails the call if it runs too long:

```python
import asyncio

from railtracks.middleware.core import Middleware


class Timeout(Middleware):
    """Fail the wrapped call if it runs longer than ``seconds``."""

    def __init__(self, seconds: float):
        self._seconds = seconds
        super().__init__(self._middleware_fn)

    async def _middleware_fn(self, call, *args, **kwargs):
        return await asyncio.wait_for(call(*args, **kwargs), timeout=self._seconds)
```

That's the recipe:

1. subclass `Middleware`.
2. pass a middleware function to `super().__init__`.
3. call `call(*args, **kwargs)` when you want the wrapped node/model to run.

Because it only re-invokes `call` and never inspects the arguments, `Timeout` is slot-agnostic; it works as both node and model middleware. A guardrail is the same idea specialized to LLM input/output; see [Contributing a Guardrail](../guardrails/contributions.md).

## Where it goes

Put your middleware in the `prebuilt/` package:

| Kind | Location | Public import path |
|---|---|---|
| Middleware | `packages/railtracks/src/railtracks/prebuilt/middleware/` | `rt.prebuilt.middleware.<Name>` |
| Guardrail | `packages/railtracks/src/railtracks/prebuilt/guardrails/` | `rt.prebuilt.guardrails.<Name>` |

Add one module per middleware and re-export the public name from that package's `__init__.py`. Then add unit tests under `packages/railtracks/tests/unit_tests/`, and a dedicated page under `docs/documentation/agent_design/middleware/prebuilt/list/` with a runnable snippet in `docs/scripts/`.

## Opening an issue / PR

We would love your contribution. Check the parent issue for [Middleware Creation (#1145)](https://github.com/RailtownAI/railtracks/issues/1145) to see what's already planned, then:

1. Open an issue describing the middleware and its use case (or comment on #1145).
2. Implement it under `prebuilt/`, with tests and a docs page as above.
3. Open a PR linking the issue.
