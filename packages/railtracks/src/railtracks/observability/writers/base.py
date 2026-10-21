from __future__ import annotations

from typing import Protocol

from ..models import Event


class Writer(Protocol):
    """A destination for events.

    Methods are called on whichever thread publishes, one call at a time per writer,
    possibly inside a running event loop. Keep them fast and free of asyncio; a writer
    that needs the network should hand events to its own thread.
    """

    def start(self) -> None: ...
    def write(self, event: Event) -> None: ...
    def shutdown(self) -> None: ...
