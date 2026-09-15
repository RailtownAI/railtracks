"""Structured logging for the beta visualizer API."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

_LOGGER = logging.getLogger("railtracks.viz_api")
_DEBUG = False


class _JsonFormatter(logging.Formatter):
    """Render one stable JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def set_debug(value: bool) -> None:
    """Configure the API logger; debug mode includes request and query timings."""
    global _DEBUG
    _DEBUG = value
    _LOGGER.setLevel(logging.DEBUG if value else logging.INFO)

    for handler in list(_LOGGER.handlers):
        if getattr(handler, "_railtracks_viz_handler", False):
            _LOGGER.removeHandler(handler)

    handler = logging.StreamHandler()
    handler._railtracks_viz_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(_JsonFormatter())
    _LOGGER.addHandler(handler)
    _LOGGER.propagate = False


def is_debug() -> bool:
    return _DEBUG


def debug_event(event: str, message: str | None = None, **fields: Any) -> None:
    """Emit a structured debug event when debug mode is active."""
    _LOGGER.debug(message or event, extra={"event": event, "fields": fields})


def warning_event(event: str, message: str, **fields: Any) -> None:
    """Emit a structured warning event."""
    _LOGGER.warning(message, extra={"event": event, "fields": fields})


def exception_event(event: str, message: str, **fields: Any) -> None:
    """Emit a structured error event with the active exception traceback."""
    _LOGGER.exception(message, extra={"event": event, "fields": fields})
