"""Unified middleware for every Railtracks entry point.

Two primitives, each attachable to any callable (function node, agent, model
call):

- :class:`Wrapper` — execution control (retry, fallback, timing,
  short-circuit).  Written as a call-style async function::

      @wrapper
      async def retry(call, *args, **kwargs):
          for _ in range(3):
              try:
                  return await call(*args, **kwargs)
              except Exception:
                  pass
          raise RuntimeError("All retries exhausted")

- :class:`Gate` — direction-neutral data transform. Place it in
  ``entry_gate`` to transform inputs before the core runs, or in
  ``exit_gate`` to transform the output afterwards.

:class:`MiddlewareChain` bundles them into an ordered execution chain::

    wrappers → entry_gate → inner_wrappers → core → exit_gate → (unwind)
"""

from railtracks.middleware.primitives import (
    Gate,
    Wrapper,
    gate,
    wrapper,
)
from railtracks.middleware.set import MiddlewareChain
from railtracks.middleware.couple import couple

__all__ = [
    "Wrapper",
    "wrapper",
    "Gate",
    "gate",
    "MiddlewareChain",
    "couple",
]
