from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from ...models import Event
from ._serialize import RTObserverEncoder


class JsonlWriter:
    def __init__(self, directory: Path):
        self._directory = directory
        self._files: dict[str, TextIO] = {}

    async def start(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)

    async def write(self, event: Event) -> None:
        handle = self._files.get(event.scope_type)
        if handle is None:
            handle = (self._directory / f"{event.scope_type}.jsonl").open(
                "a", encoding="utf-8"
            )
            self._files[event.scope_type] = handle
        handle.write(_serialize(event) + "\n")
        handle.flush()

    async def shutdown(self) -> None:
        for handle in self._files.values():
            handle.flush()
            handle.close()
        self._files.clear()


def _serialize(event: Event) -> str:
    return json.dumps(event, cls=RTObserverEncoder)
