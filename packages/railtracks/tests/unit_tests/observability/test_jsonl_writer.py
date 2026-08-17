import json
from datetime import datetime
from pathlib import Path

import pytest

from railtracks.observability import (
    SCOPE_RETRIEVAL,
    SCOPE_SESSION,
    Event,
    JsonlWriter,
    Timestamp,
)


def _make_session_event(scope_type: str, scope_id: str = "id-1", **kw) -> Event:
    return Event(
        event_type=kw.pop("event_type", "test.event"),
        stamp=Timestamp.now(),
        scope_type=scope_type,
        scope_id=scope_id,
        **kw,
    )


def _parse_line(line: str) -> Event:
    data = json.loads(line)
    data["stamp"] = datetime.fromisoformat(data["stamp"])
    return Event(**data)


async def test_start_creates_directory(tmp_path: Path):
    target = tmp_path / "nested" / "dir"
    writer = JsonlWriter(target)
    await writer.start()
    try:
        assert target.is_dir()
    finally:
        await writer.shutdown()


async def test_write_creates_per_scope_id_files(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    await writer.start()
    try:
        await writer.write(_make_session_event(SCOPE_SESSION, scope_id="sess-1"))
        await writer.write(_make_session_event(SCOPE_RETRIEVAL, scope_id="ret-1"))
    finally:
        await writer.shutdown()

    assert (tmp_path / "sess-1.jsonl").exists()
    assert (tmp_path / "ret-1.jsonl").exists()


async def test_one_line_per_event(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    await writer.start()
    try:
        for _ in range(5):
            await writer.write(_make_session_event(SCOPE_SESSION, scope_id="s1"))
    finally:
        await writer.shutdown()

    lines = (tmp_path / "s1.jsonl").read_text().splitlines()
    assert len(lines) == 5


async def test_each_line_round_trips_to_original_event(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    await writer.start()
    original = _make_session_event(
        SCOPE_SESSION,
        payload={"nested": {"k": "v"}, "list": [1, 2, 3]},
        parent_scope_id="parent-1",
    )
    try:
        await writer.write(original)
    finally:
        await writer.shutdown()

    lines = (tmp_path / "id-1.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert _parse_line(lines[0]) == original


async def test_append_across_writer_lifecycles(tmp_path: Path):
    first = JsonlWriter(tmp_path)
    await first.start()
    await first.write(
        _make_session_event(SCOPE_SESSION, scope_id="s1", event_type="first")
    )
    await first.shutdown()

    second = JsonlWriter(tmp_path)
    await second.start()
    await second.write(
        _make_session_event(SCOPE_SESSION, scope_id="s1", event_type="second")
    )
    await second.shutdown()

    lines = (tmp_path / "s1.jsonl").read_text().splitlines()
    assert [_parse_line(line).event_type for line in lines] == ["first", "second"]


async def test_shutdown_closes_handles(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    await writer.start()
    await writer.write(_make_session_event(SCOPE_SESSION, scope_id="s1"))
    handle = writer._files["s1"]
    await writer.shutdown()
    assert handle.closed
    assert writer._files == {}


async def test_flush_makes_bytes_readable_before_shutdown(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    await writer.start()
    try:
        await writer.write(_make_session_event(SCOPE_SESSION, scope_id="s1"))
        lines = (tmp_path / "s1.jsonl").read_text().splitlines()
        assert len(lines) == 1
    finally:
        await writer.shutdown()


@pytest.mark.parametrize(
    "bad_scope_id",
    [
        "",
        ".",
        "..",
        ".hidden",
        "../escape",
        "a/b",
        "a\\b",
        "with\x00null",
    ],
)
async def test_write_rejects_unsafe_scope_id(tmp_path: Path, bad_scope_id: str):
    writer = JsonlWriter(tmp_path)
    await writer.start()
    try:
        with pytest.raises(ValueError, match="unsafe scope_id"):
            await writer.write(_make_session_event(SCOPE_SESSION, scope_id=bad_scope_id))
        assert list(tmp_path.iterdir()) == []
    finally:
        await writer.shutdown()
