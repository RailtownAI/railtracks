from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from ...models import Event
from ...storage import MEDIA_SUBDIR, resolve_events_dir
from ._media import MediaStore, save_media_max_bytes
from ._serialize import RTObserverEncoder


class JsonlWriter:
    def __init__(
        self, directory: Path | None = None, media_directory: Path | None = None
    ):
        """Write events to ``directory`` or the shared visualizer event store.

        Media in the events is recorded as metadata and a content hash, and its
        bytes are saved once per hash to ``media_directory``, by default a
        ``media`` folder inside the events directory. ``RAILTRACKS_MEDIA_MAX_MB``
        caps the size saved: unset saves everything, ``0`` saves nothing.
        """
        self._directory = directory if directory is not None else resolve_events_dir()
        self._media = MediaStore(
            media_directory
            if media_directory is not None
            else self._directory / MEDIA_SUBDIR,
            save_media_max_bytes(),
        )
        self._files: dict[str, TextIO] = {}

    async def start(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)

    async def write(self, event: Event) -> None:
        handle = self._files.get(event.scope_id)
        if handle is None:
            _check_safe_scope_id(event.scope_id)
            # Unpaired surrogates cannot be encoded; keep them as \u escapes
            handle = (self._directory / f"{event.scope_id}.jsonl").open(
                "a", encoding="utf-8", errors="backslashreplace"
            )
            self._files[event.scope_id] = handle
        handle.write(_serialize(event, self._media) + "\n")
        handle.flush()

    async def shutdown(self) -> None:
        for handle in self._files.values():
            handle.flush()
            handle.close()
        self._files.clear()


def _serialize(event: Event, media: MediaStore) -> str:
    return json.dumps(event, cls=RTObserverEncoder, ensure_ascii=False, media=media)


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
