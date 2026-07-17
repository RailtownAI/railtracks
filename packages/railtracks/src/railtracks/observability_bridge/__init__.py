"""Bridge between the framework-agnostic `railtracks.observability` module and
the railtracks runtime — reads scope from InternalContext, owns the process-wide
Observer, and provides the emission call site."""

from ._factory import make_event
from ._state import configure_writers

__all__ = ["configure_writers", "make_event"]
