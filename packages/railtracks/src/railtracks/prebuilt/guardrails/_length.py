"""Shared character-counting helpers for length guardrails."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from railtracks.llm.content import ToolCalls, ToolResponse


def message_char_count(content: Any) -> int:
    """Return the number of characters represented by a message content value.

    Handles the various shapes that appear in message histories:

    - ``None`` → 0
    - ``str`` → ``len(content)``
    - ``ToolResponse`` → ``len(content.result)`` (result is str or bytes)
    - ``ToolCalls`` → text length plus, for each call, name + json of arguments
    - ``BaseModel`` → length of the model_dump_json()
    - anything else → ``len(str(content))``

    ``ToolCalls`` is checked before the generic list path because it is a
    ``list`` subclass.
    """
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    if isinstance(content, ToolResponse):
        result = content.result
        if isinstance(result, bytes):
            return len(result)
        return len(str(result))
    if isinstance(content, ToolCalls):
        total = len(content.text or "")
        for call in content:
            total += len(call.name)
            total += len(json.dumps(call.arguments, default=str))
        return total
    if isinstance(content, BaseModel):
        return len(content.model_dump_json())
    return len(str(content))
