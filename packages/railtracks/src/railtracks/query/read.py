from __future__ import annotations

import json
from pathlib import Path

_SAMPLES_DIR = Path(__file__).parent / "_samples"


def _sample_files() -> list[Path]:
    if not _SAMPLES_DIR.is_dir():
        return []
    return sorted(_SAMPLES_DIR.glob("*.jsonl"))


def _resolve_data_files(path: Path | str) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(p.glob("*.jsonl"))
    return []


def _scan(files: list[Path]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in files:
        with path.open(encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_type = event.get("event_type") or ""
                if "." not in event_type:
                    continue
                namespace = event_type.split(".", 1)[0]
                bucket = result.setdefault(namespace, set())
                payload = event.get("payload")
                if isinstance(payload, dict):
                    bucket.update(payload.keys())
    return result


def list_namespaces(path: Path | str) -> list[str]:
    """Union of namespaces in the bundled samples and in ``path``."""
    files = _sample_files() + _resolve_data_files(path)
    return sorted(_scan(files).keys())
