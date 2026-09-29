import json
from pathlib import Path

import pytest
from railtracks.utils.json.files import read_json, to_json, write_json_text

READABLE = "你好, こんにちは 😀 café"


def test_to_json_keeps_non_ascii_text_as_written():
    assert to_json({"text": READABLE}) == f'{{"text": "{READABLE}"}}'


@pytest.mark.parametrize("line_break", ["\x85", " ", " "])
def test_to_json_keeps_a_record_on_one_line(line_break: str):
    value = {"text": f"before{line_break}after"}

    text = to_json(value)

    assert text.splitlines() == [text]
    assert json.loads(text) == value


def test_write_json_text_writes_utf8_without_a_bom(tmp_path: Path):
    path = tmp_path / "data.json"

    write_json_text(path, to_json({"text": READABLE}))

    raw = path.read_bytes()
    assert raw.startswith(b"{")
    assert READABLE.encode("utf-8") in raw


def test_lone_surrogate_is_written_as_the_escape_json_dumps_uses(tmp_path: Path):
    value = {"text": "half an emoji \ud83d"}
    path = tmp_path / "data.json"

    write_json_text(path, to_json(value))

    assert path.read_bytes() == json.dumps(value).encode("ascii")
    assert read_json(path) == value


def test_read_json_reads_ascii_escaped_files(tmp_path: Path):
    value = {"text": READABLE}
    path = tmp_path / "legacy.json"
    path.write_bytes(json.dumps(value).encode("ascii"))

    assert read_json(path) == value


def test_read_json_reads_utf8_whatever_the_locale(tmp_path: Path):
    value = {"text": READABLE}
    path = tmp_path / "data.json"
    path.write_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    assert read_json(path) == value


def test_read_json_reports_a_file_cut_mid_character_as_value_error(tmp_path: Path):
    raw = to_json({"text": READABLE}).encode("utf-8")
    path = tmp_path / "partial.json"
    path.write_bytes(raw[: raw.index("你".encode("utf-8")) + 1])

    with pytest.raises(ValueError):
        read_json(path)
