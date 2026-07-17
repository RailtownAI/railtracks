"""Bridge between the framework-agnostic `railtracks.observability` module and
the railtracks agent runtime.

Reads scope from `InternalContext` to build `Event` objects. The observability
module itself handles the singleton Observer, writer registration, and event
publishing — this module just does the framework-aware step of turning a
(type, payload) pair into a scoped Event.
"""

from ._factory import make_event

__all__ = ["make_event"]
