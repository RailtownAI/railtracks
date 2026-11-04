"""Media bytes from the event record, stored once per content hash."""

from __future__ import annotations

import logging
import math
import os
import re
import tempfile
import warnings
from pathlib import Path
from typing import Callable

logger = logging.getLogger(f"RT.{__name__}")

MEDIA_MAX_MB_ENV = "RAILTRACKS_MEDIA_MAX_MB"

_SHA256 = re.compile(r"[0-9a-f]{64}")


def save_media_max_bytes() -> int | None:
    """Parse RAILTRACKS_MEDIA_MAX_MB into a byte limit. Unset means no limit,
    and so does anything other than a non-negative number of megabytes, with a warning."""
    raw = os.environ.get(MEDIA_MAX_MB_ENV, "").strip()
    if not raw:
        return None

    try:
        max_mb = float(raw)
    except ValueError:
        max_mb = math.nan
    if not 0 <= max_mb < math.inf:
        warnings.warn(
            f"{MEDIA_MAX_MB_ENV}={raw!r} is not a non-negative number of megabytes; saving all media.",
            stacklevel=2,
        )
        return None
    return int(max_mb * 1024 * 1024)


class MediaStore:
    """Writes each piece of media once, named by its SHA-256 with no extension."""

    def __init__(self, directory: Path, max_bytes: int | None = None):
        """Store media in ``directory``.

        Args:
            directory: The folder to write media into. Created on the first write.
            max_bytes: Largest media stored, in bytes, or None for no limit.
        """
        self._directory = directory
        self._max_bytes = max_bytes
        self._stored: set[str] = set()

    def save(self, sha256: str, size: int, data: Callable[[], bytes]) -> None:
        """Store media bytes under their content hash, unless over the size limit.

        Nothing is stored when `sha256` is not a hex SHA-256, and a failed write
        is logged as a warning.

        Args:
            sha256: The hex SHA-256 of the bytes.
            size: The number of bytes, checked against the limit before `data` is
                called.
            data: Returns the bytes. Only called when they still need writing.
        """
        if self._max_bytes is not None and size > self._max_bytes:
            return
        if sha256 in self._stored:
            return
        if not _SHA256.fullmatch(sha256):
            return

        path = self._directory / sha256
        try:
            if not path.exists():
                self._directory.mkdir(parents=True, exist_ok=True)
                _write_atomically(path, data())
        except OSError as e:
            logger.warning("Could not save media %s: %r", path, e)
            return

        self._stored.add(sha256)


def _write_atomically(path: Path, content: bytes) -> None:
    """Write `content` to `path` through a temporary file, so `path` never holds part of it."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
