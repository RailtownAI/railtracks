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

- :class:`Gateway` — direction-neutral data transform. Place it in
  ``gateway_entry`` to transform inputs before the core runs, or in
  ``gateway_exit`` to transform the output afterwards.

:class:`MiddlewareSet` bundles them into an ordered execution chain::

    wrappers → gateway_entry → inner_wrappers → core → gateway_exit → (unwind)
"""

from railtracks.middleware.primitives import (
    Gateway,
    Wrapper,
    gateway,
    wrapper,
)
from railtracks.middleware.set import MiddlewareSet

__all__ = [
    "Wrapper",
    "wrapper",
    "Gateway",
    "gateway",
    "MiddlewareSet",
]
