"""Unified middleware: two primitives (`Wrapper`, `Gateway`) attachable to every
entry point, plus the `MiddlewareSet` container that orders and runs them."""

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
