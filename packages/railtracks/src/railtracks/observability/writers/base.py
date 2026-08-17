from __future__ import annotations

from typing import Protocol

from ..models import Event


class Writer(Protocol):
    async def start(self) -> None: ...
    async def write(self, event: Event) -> None: ...
    async def shutdown(self) -> None: ...
