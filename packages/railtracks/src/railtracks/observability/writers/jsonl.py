from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from ..models import Event


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
    return json.dumps(dataclasses.asdict(event), default=_json_default)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
