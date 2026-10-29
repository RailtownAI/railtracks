import base64
import hashlib
import json
import logging
from pathlib import Path

import pytest
from railtracks.events.context import _snapshot
from railtracks.llm import MessageHistory, UserMessage
from railtracks.observability import (
    EVENTS_DIR_ENV,
    SCOPE_SESSION,
    Event,
    JsonlWriter,
    resolve_media_dir,
)
from railtracks.observability.writers.jsonl._media import (
    MEDIA_MAX_MB_ENV,
    MediaStore,
    save_media_max_bytes,
)
from railtracks.utils.json.encoder import RTJSONEncoder

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PNG_SHA256 = hashlib.sha256(PNG_BYTES).hexdigest()
PNG_B64 = base64.b64encode(PNG_BYTES).decode()


@pytest.fixture
def png_path(tmp_path: Path) -> str:
    path = tmp_path / "before.png"
    path.write_bytes(PNG_BYTES)
    return str(path)


def _llm_event(*attachments: str) -> Event:
    message = UserMessage("describe", attachment=list(attachments))
    return Event(
        event_type="llm.invocation",
        scope_type=SCOPE_SESSION,
        scope_id="session-1",
        payload={"message_input": MessageHistory([message])},
    )


async def _write(writer: JsonlWriter, *events: Event) -> list[dict]:
    await writer.start()
    try:
        for event in events:
            await writer.write(event)
    finally:
        await writer.shutdown()
    lines = (writer._directory / "session-1.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


def _media_parts(line: dict) -> list[dict]:
    [message] = line["payload"]["message_input"]
    return message["content"][1:]


async def test_media_is_saved_once_and_recorded_by_hash(tmp_path: Path, png_path):
    media_dir = tmp_path / "media"
    writer = JsonlWriter(tmp_path / "events", media_directory=media_dir)

    lines = await _write(writer, _llm_event(png_path), _llm_event(png_path))

    assert [p.name for p in media_dir.iterdir()] == [PNG_SHA256]
    assert (media_dir / PNG_SHA256).read_bytes() == PNG_BYTES
    for line in lines:
        [part] = _media_parts(line)
        assert part["sha256"] == PNG_SHA256


async def test_inline_bytes_never_reach_the_jsonl(tmp_path: Path):
    writer = JsonlWriter(tmp_path / "events", media_directory=tmp_path / "media")

    await _write(writer, _llm_event(f"data:image/png;base64,{PNG_B64}"))

    text = (tmp_path / "events" / "session-1.jsonl").read_text()
    assert PNG_B64 not in text
    assert PNG_SHA256 in text


async def test_existing_media_file_is_not_rewritten(tmp_path: Path, png_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    existing = media_dir / PNG_SHA256
    existing.write_bytes(b"written by an earlier run")
    writer = JsonlWriter(tmp_path / "events", media_directory=media_dir)

    await _write(writer, _llm_event(png_path))

    assert existing.read_bytes() == b"written by an earlier run"


async def test_limit_of_zero_saves_metadata_only(
    tmp_path: Path, png_path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv(MEDIA_MAX_MB_ENV, "0")
    media_dir = tmp_path / "media"
    writer = JsonlWriter(tmp_path / "events", media_directory=media_dir)

    [line] = await _write(writer, _llm_event(png_path))

    [part] = _media_parts(line)
    assert part["sha256"] == PNG_SHA256
    assert not media_dir.exists()


async def test_limit_saves_media_up_to_the_size(
    tmp_path: Path, png_path, monkeypatch: pytest.MonkeyPatch
):
    large = tmp_path / "large.png"
    large.write_bytes(PNG_BYTES + b"\x00" * 1000)
    monkeypatch.setenv(MEDIA_MAX_MB_ENV, str(500 / (1024 * 1024)))
    media_dir = tmp_path / "media"
    writer = JsonlWriter(tmp_path / "events", media_directory=media_dir)

    await _write(writer, _llm_event(png_path, str(large)))

    assert [p.name for p in media_dir.iterdir()] == [PNG_SHA256]


async def test_media_is_saved_inside_the_events_dir_by_default(
    tmp_path: Path, png_path
):
    writer = JsonlWriter(tmp_path / "events")

    await _write(writer, _llm_event(png_path))

    assert (tmp_path / "events" / "media" / PNG_SHA256).exists()


def test_media_dir_follows_events_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RAILTRACKS_HOME", str(tmp_path))
    monkeypatch.delenv(EVENTS_DIR_ENV, raising=False)
    assert resolve_media_dir() == tmp_path / ".railtracks" / "data" / "events" / "media"

    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path / "saved-events"))
    assert resolve_media_dir() == tmp_path / "saved-events" / "media"


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, None),
        ("", None),
        ("0", 0),
        ("20", 20 * 1024 * 1024),
        ("0.5", 512 * 1024),
    ],
)
def test_save_media_max_bytes(raw, expected, monkeypatch: pytest.MonkeyPatch):
    if raw is None:
        monkeypatch.delenv(MEDIA_MAX_MB_ENV, raising=False)
    else:
        monkeypatch.setenv(MEDIA_MAX_MB_ENV, raw)
    assert save_media_max_bytes() == expected


@pytest.mark.parametrize("raw", ["lots", "-1", "nan", "inf"])
def test_invalid_limit_warns_and_saves_everything(raw, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(MEDIA_MAX_MB_ENV, raw)
    with pytest.warns(UserWarning, match=MEDIA_MAX_MB_ENV):
        assert save_media_max_bytes() is None


def test_store_rejects_names_that_are_not_a_hash(tmp_path: Path):
    store = MediaStore(tmp_path)

    store.save("../escape", 3, lambda: b"abc")

    assert list(tmp_path.iterdir()) == []


def test_store_reports_a_failed_write(tmp_path: Path, caplog):
    not_a_dir = tmp_path / "media"
    not_a_dir.write_text("in the way")
    store = MediaStore(not_a_dir)

    with caplog.at_level(logging.WARNING):
        store.save(PNG_SHA256, len(PNG_BYTES), lambda: PNG_BYTES)

    assert "Could not save media" in caplog.text


def test_session_json_encoder_keeps_the_legacy_shape(png_path):
    message = UserMessage("describe", attachment=png_path)

    encoded = json.loads(json.dumps(message, cls=RTJSONEncoder))

    assert encoded["content"][1] == {
        "modality": "image",
        "type": "local",
        "info": png_path,
    }


def test_context_snapshot_records_media_without_bytes():
    message = UserMessage("describe", attachment=f"data:image/png;base64,{PNG_B64}")

    snapshot = _snapshot(message)

    part = snapshot["content"][1]
    assert part["sha256"] == PNG_SHA256
    assert PNG_B64 not in json.dumps(snapshot)
