"""Content extraction strategies for structured loader fields."""

from __future__ import annotations

import json
from typing import Any, Protocol


class ContentExtractor(Protocol):
    """Convert one loader field value into searchable text."""

    def __call__(self, value: Any, /) -> str: ...


class StrExtractor:
    """Render values with Python's built-in string conversion."""

    def __call__(self, value: Any) -> str:
        return str(value)


class JsonExtractor:
    """Render values as valid JSON while preserving Unicode text."""

    def __call__(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)


class ProseExtractor:
    """Flatten nested JSON-like values into readable, labelled text."""

    def __call__(self, value: Any) -> str:
        return self._render(value, nested=False)

    def _render(self, value: Any, *, nested: bool = True) -> str:
        if isinstance(value, dict):
            rendered = "; ".join(
                f"{key}: {self._render(item)}" for key, item in value.items()
            )
            return f"{{{rendered}}}" if nested else rendered
        if isinstance(value, (list, tuple)):
            return f"[{', '.join(self._render(item) for item in value)}]"
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
