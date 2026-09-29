"""Encoding for the JSON files railtracks keeps on disk.

Session dumps, the event stream, evaluation results and store snapshots are all
UTF-8, with non-ASCII text stored as written rather than as ``\\uXXXX`` escapes,
so emoji and non-English text stay readable to the people and agents opening
them. UTF-8 is what JSON (RFC 8259), DuckDB and browsers read. A file written
with escapes is plain ASCII, which is also valid UTF-8, so older files read back
unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JSON_ENCODING = "utf-8"

#: Lone surrogates are the only text UTF-8 cannot encode. This writes them as the
#: ``\uXXXX`` escape ``json.dumps`` produces by default, which decodes back.
JSON_ENCODING_ERRORS = "backslashreplace"

#: Left raw once ``ensure_ascii`` is off, yet split by ``str.splitlines`` and
#: flagged by editors as line terminators, so they stay escaped.
_LINE_BREAKS = ("\x85", " ", " ")


def to_json(obj: object, *, cls: type[json.JSONEncoder] | None = None) -> str:
    """Serialize ``obj`` to single-line JSON, keeping non-ASCII text as written.

    Args:
        obj: The value to serialize.
        cls: An encoder for values the standard one cannot serialize.

    Returns:
        The JSON text, with no raw character that a line reader splits on.
    """
    text = json.dumps(obj, cls=cls, ensure_ascii=False)
    for char in _LINE_BREAKS:
        text = text.replace(char, f"\\u{ord(char):04x}")
    return text


def write_json_text(path: Path, text: str) -> None:
    """Write JSON text from :func:`to_json` to ``path``, replacing any existing file.

    Args:
        path: The file to write.
        text: The serialized JSON.
    """
    path.write_text(text, encoding=JSON_ENCODING, errors=JSON_ENCODING_ERRORS)


def read_json(path: Path) -> Any:
    """Read a JSON file railtracks wrote, whether its text is escaped or not.

    Args:
        path: The file to read.

    Returns:
        The decoded JSON value.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the file is not valid UTF-8 or not valid JSON, for
            example when it is read while still being written.
    """
    return json.loads(path.read_text(encoding=JSON_ENCODING))
