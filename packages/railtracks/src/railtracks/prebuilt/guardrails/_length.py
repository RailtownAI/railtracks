"""Shared character-counting helpers for length guardrails.

Message content is not always a ``str``: tool turns carry ``ToolResponse`` /
``ToolCalls``, and structured-output turns carry a pydantic ``BaseModel``.
``len()`` on those types either raises ``TypeError`` or counts the wrong unit
(number of tool calls).  Both ``InputLengthGuard`` and ``OutputLengthGuard``
route through :func:`message_char_count` so they stay consistent.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from railtracks.llm.content import ToolCalls, ToolResponse


def message_char_count(content: Any) -> int:
    """Return a character count for a message's ``content`` field.

    | Content | Count |
    |---|---|
    | ``None`` | ``0`` |
    | ``str`` | ``len(content)`` |
    | ``ToolResponse`` | ``len(content.result)`` (``result`` is ``str`` or ``bytes``) |
    | ``ToolCalls`` | ``len(content.text or "")`` plus, for each call,
      ``len(call.name)`` + ``len(json.dumps(call.arguments, default=str))`` |
    | ``BaseModel`` | ``len(content.model_dump_json())`` |
    | anything else | ``len(str(content))`` |

    ``ToolCalls`` is checked before the generic list/object fallback because it
    is a ``list`` subclass.
    """
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    if isinstance(content, ToolResponse):
        result = content.result
        if isinstance(result, bytes):
            return len(result)
        return len(result or "")
    if isinstance(content, ToolCalls):
        total = len(content.text or "")
        for call in content:
            total += len(call.name)
            total += len(json.dumps(call.arguments, default=str))
        return total
    if isinstance(content, BaseModel):
        return len(content.model_dump_json())
    return len(str(content))
