from __future__ import annotations

from pathlib import Path

from railtracks.events.registry import namespaces as _registry_namespaces


def _resolve_data_files(path: Path | str) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(p.glob("*.jsonl"))
    return []


def list_namespaces(_path: Path | str | None = None) -> list[str]:
    """Return the namespaces backed by an event dataclass in ``railtracks.events``.

    The ``path`` argument is accepted for signature stability but ignored — namespace
    membership is now static, driven by the registry.
    """
    return _registry_namespaces()
