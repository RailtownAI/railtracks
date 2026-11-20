"""Shared character-counting helpers for length guardrails.

Message content is not always text: every message holds a list of text, attachments
and tool calls, and structured-output turns hold a pydantic ``BaseModel``. ``len()``
on those either raises ``TypeError`` or counts the wrong unit (number of parts).
Both ``InputLengthGuard`` and ``OutputLengthGuard`` route through
:func:`message_char_count` so they stay consistent.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from railtracks.llm.content import ToolCall
from railtracks.llm.message import content_text


def message_char_count(content: Any) -> int:
    """Return a character count for a message's ``content`` field.

    | Content | Count |
    |---|---|
    | ``None`` | ``0`` |
    | ``str`` | ``len(content)`` |
    | list of parts | ``len`` of the message text, plus ``len(call.name)`` +
      ``len(json.dumps(call.arguments, default=str))`` for each tool call;
      attachments count ``0`` |
    | ``BaseModel`` | ``len(content.model_dump_json())`` |
    | anything else | ``len(str(content))`` |
    """
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = len(content_text(content))
        for part in content:
            if isinstance(part, ToolCall):
                total += len(part.name)
                total += len(json.dumps(part.arguments, default=str))
        return total
    if isinstance(content, BaseModel):
        return len(content.model_dump_json())
    return len(str(content))
