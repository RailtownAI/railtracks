"""Character counting for message content, shared by the prebuilt length guards."""

from __future__ import annotations

from railtracks.llm.content import ToolCalls


def content_length(content: object) -> int:
    """Return the character count of a message's content.

    Message content is not always a ``str``: tool responses, tool-calling turns and
    structured outputs carry other shapes, so ``len(content)`` raises or miscounts
    for them. This renders each shape to its text form so a length guard can measure
    every message without raising.

    Args:
        content: A message's content — a ``str``, ``ToolResponse``, ``ToolCalls``,
            ``list[ToolCall]``, pydantic model, or ``None``.

    Returns:
        The number of characters in the content's text form.
    """
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    if isinstance(content, ToolCalls):
        parts = [str(call) for call in content]
        if content.text:
            parts.append(content.text)
        return len(" ".join(parts))
    if isinstance(content, list):
        return len(" ".join(str(item) for item in content))
    return len(str(content))
