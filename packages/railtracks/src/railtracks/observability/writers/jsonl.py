from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import TextIO

from ..models import Event


class JsonlWriter:
    def __init__(self, directory: Path):
        self._directory = directory
        self._files: dict[str, TextIO] = {}

    async def start(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)

    async def write(self, event: Event) -> None:
        handle = self._files.get(event.scope_id)
        if handle is None:
            _check_safe_scope_id(event.scope_id)
            handle = (self._directory / f"{event.scope_id}.jsonl").open(
                "a", encoding="utf-8"
            )
            self._files[event.scope_id] = handle
        handle.write(_serialize(event) + "\n")
        handle.flush()

    async def shutdown(self) -> None:
        for handle in self._files.values():
            handle.flush()
            handle.close()
        self._files.clear()


def _serialize(event: Event) -> str:
    data = dataclasses.asdict(event)
    data["stamp"] = event.stamp.isoformat()
    return json.dumps(data)


_UNSAFE_SCOPE_ID_CHARS = frozenset("/\\\0")


def _check_safe_scope_id(scope_id: str) -> None:
    if (
        not scope_id
        or scope_id in (".", "..")
        or scope_id.startswith(".")
        or any(c in _UNSAFE_SCOPE_ID_CHARS for c in scope_id)
    ):
        raise ValueError(
            f"unsafe scope_id for filesystem writer: {scope_id!r}; "
            "must be non-empty, must not start with '.', "
            "and must not contain path separators or null bytes"
        )
