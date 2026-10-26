import json
from datetime import datetime
from pathlib import Path

import pytest
from railtracks.observability import (
    EVENTS_DIR_ENV,
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


def test_start_creates_directory(tmp_path: Path):
    target = tmp_path / "nested" / "dir"
    writer = JsonlWriter(target)
    writer.start()
    try:
        assert target.is_dir()
    finally:
        writer.shutdown()


def test_default_directory_matches_visualizer_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))
    writer = JsonlWriter()

    writer.start()
    try:
        writer.write(_make_session_event(SCOPE_SESSION, scope_id="default"))
    finally:
        writer.shutdown()

    assert (tmp_path / "default.jsonl").exists()


def test_write_creates_per_scope_id_files(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    writer.start()
    try:
        writer.write(_make_session_event(SCOPE_SESSION, scope_id="sess-1"))
        writer.write(_make_session_event(SCOPE_RETRIEVAL, scope_id="ret-1"))
    finally:
        writer.shutdown()

    assert (tmp_path / "sess-1.jsonl").exists()
    assert (tmp_path / "ret-1.jsonl").exists()


def test_one_line_per_event(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    writer.start()
    try:
        for _ in range(5):
            writer.write(_make_session_event(SCOPE_SESSION, scope_id="s1"))
    finally:
        writer.shutdown()

    lines = (tmp_path / "s1.jsonl").read_text().splitlines()
    assert len(lines) == 5


def test_each_line_round_trips_to_original_event(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    writer.start()
    original = _make_session_event(
        SCOPE_SESSION,
        payload={"nested": {"k": "v"}, "list": [1, 2, 3]},
        parent_scope_id="parent-1",
    )
    try:
        writer.write(original)
    finally:
        writer.shutdown()

    lines = (tmp_path / "id-1.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert _parse_line(lines[0]) == original


def test_non_ascii_payload_is_stored_as_readable_utf8(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    writer.start()
    original = _make_session_event(SCOPE_SESSION, payload={"text": "你好 😀"})
    try:
        writer.write(original)
    finally:
        writer.shutdown()

    raw = (tmp_path / "id-1.jsonl").read_bytes()
    assert "你好 😀".encode("utf-8") in raw
    assert _parse_line(raw.decode("utf-8")) == original


def test_lone_surrogate_in_payload_is_written_not_raised(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    writer.start()
    original = _make_session_event(SCOPE_SESSION, payload={"text": "cut \ud83d"})
    try:
        writer.write(original)
    finally:
        writer.shutdown()

    raw = (tmp_path / "id-1.jsonl").read_bytes()
    assert _parse_line(raw.decode("utf-8")) == original


def test_append_across_writer_lifecycles(tmp_path: Path):
    first = JsonlWriter(tmp_path)
    first.start()
    first.write(_make_session_event(SCOPE_SESSION, scope_id="s1", event_type="first"))
    first.shutdown()

    second = JsonlWriter(tmp_path)
    second.start()
    second.write(_make_session_event(SCOPE_SESSION, scope_id="s1", event_type="second"))
    second.shutdown()

    lines = (tmp_path / "s1.jsonl").read_text().splitlines()
    assert [_parse_line(line).event_type for line in lines] == ["first", "second"]


def test_shutdown_closes_handles(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    writer.start()
    writer.write(_make_session_event(SCOPE_SESSION, scope_id="s1"))
    handle = writer._files["s1"]
    writer.shutdown()
    assert handle.closed
    assert writer._files == {}


def test_flush_makes_bytes_readable_before_shutdown(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    writer.start()
    try:
        writer.write(_make_session_event(SCOPE_SESSION, scope_id="s1"))
        lines = (tmp_path / "s1.jsonl").read_text().splitlines()
        assert len(lines) == 1
    finally:
        writer.shutdown()


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
def test_write_rejects_unsafe_scope_id(tmp_path: Path, bad_scope_id: str):
    writer = JsonlWriter(tmp_path)
    writer.start()
    try:
        with pytest.raises(ValueError, match="unsafe scope_id"):
            writer.write(_make_session_event(SCOPE_SESSION, scope_id=bad_scope_id))
        assert list(tmp_path.iterdir()) == []
    finally:
        writer.shutdown()


def test_start_propagates_mkdir_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """JsonlWriter.start() surfaces the mkdir OSError to its caller. Higher
    layers (Observer.start) are what catch it and route to the shared helper."""
    target = tmp_path / "unwritable" / "events"
    writer = JsonlWriter(target)

    original_mkdir = Path.mkdir

    def _refuse(self, *args, **kwargs):
        if self == target:
            raise OSError(30, "Read-only file system")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _refuse)
    with pytest.raises(OSError, match="Read-only file system"):
        writer.start()


def test_session_completed_closes_the_sessions_file(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    writer.start()
    writer.write(_make_session_event(SCOPE_SESSION, scope_id="s1"))
    handle = writer._files["s1"]

    writer.write(
        _make_session_event(
            SCOPE_SESSION, scope_id="s1", event_type="session.completed"
        )
    )

    assert handle.closed
    assert "s1" not in writer._files
    writer.shutdown()


def test_a_late_event_after_completion_appends_to_the_same_file(tmp_path: Path):
    writer = JsonlWriter(tmp_path)
    writer.start()
    writer.write(
        _make_session_event(
            SCOPE_SESSION, scope_id="s1", event_type="session.completed"
        )
    )
    writer.write(_make_session_event(SCOPE_SESSION, scope_id="s1", event_type="late"))
    writer.shutdown()

    lines = (tmp_path / "s1.jsonl").read_text().splitlines()
    assert [_parse_line(line).event_type for line in lines] == [
        "session.completed",
        "late",
    ]
