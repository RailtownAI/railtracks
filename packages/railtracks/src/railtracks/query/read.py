from __future__ import annotations

from pathlib import Path


def resolve_data_files(path: Path | str) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(p.glob("*.jsonl"))
    return []

