"""Bridge between the framework-agnostic `railtracks.observability` module and
the railtracks runtime — reads scope from InternalContext, owns the process-wide
Observer, and provides the emission call site."""

from ._factory import make_event

__all__ = ["make_event"]
