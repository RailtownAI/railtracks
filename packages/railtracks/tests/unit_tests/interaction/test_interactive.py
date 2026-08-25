"""Unit tests for railtracks.interaction.interactive.

`local_chat`/`_chat_ui_interactive` are stubbed (they `raise NotImplementedError`
immediately) -- the old implementation code that used to sit below those raises
was dead/unreachable and has been removed. `_process_attachment` is still a
live, reachable helper (it just lost its only test coverage when the old
`test_interactive.py`, which drove it only indirectly through the now-dead
`_chat_ui_interactive` body, was deleted), so it gets direct coverage here.
"""

from __future__ import annotations

import pytest
from railtracks.human_in_the_loop.local_chat_ui import UserMessageAttachment
from railtracks.interaction.interactive import (
    _chat_ui_interactive,
    _process_attachment,
    local_chat,
)
from railtracks.nodes.nodes import Node


def test_process_attachment_file_returns_data():
    attachment = UserMessageAttachment(type="file", data="base64data")
    assert _process_attachment([attachment]) == ["base64data"]


def test_process_attachment_url_returns_url():
    attachment = UserMessageAttachment(type="url", url="https://example.com/x")
    assert _process_attachment([attachment]) == ["https://example.com/x"]


def test_process_attachment_mixed_list_preserves_order():
    attachments = [
        UserMessageAttachment(type="file", data="d1"),
        UserMessageAttachment(type="url", url="u1"),
        UserMessageAttachment(type="file", data="d2"),
    ]
    assert _process_attachment(attachments) == ["d1", "u1", "d2"]


def test_process_attachment_empty_list_returns_empty_list():
    assert _process_attachment([]) == []


@pytest.mark.asyncio
async def test_local_chat_raises_not_implemented():
    class DummyNode(Node):
        pass

    with pytest.raises(NotImplementedError):
        await local_chat(DummyNode)


@pytest.mark.asyncio
async def test_chat_ui_interactive_raises_not_implemented():
    class DummyNode(Node):
        pass

    with pytest.raises(NotImplementedError):
        await _chat_ui_interactive(None, DummyNode, None, None, None)
