"""Import boundary test for retrieval/stores.

Asserts that retrieval/stores has zero imports from engine-internal packages.
"""

from __future__ import annotations

import ast
from pathlib import Path

_FORBIDDEN_PREFIXES = (
    "railtracks.orchestration",
    "railtracks.nodes",
    "railtracks.state",
    "railtracks._session",
    "railtracks.built_nodes",
)

_STORES_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "railtracks"
    / "retrieval"
    / "stores"
)


def _collect_imports(filepath: Path) -> list[str]:
    source = filepath.read_text()
    tree = ast.parse(source, filename=str(filepath))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


def test_no_engine_imports():
    violations: list[str] = []
    for pyfile in _STORES_ROOT.rglob("*.py"):
        for module in _collect_imports(pyfile):
            for prefix in _FORBIDDEN_PREFIXES:
                if module == prefix or module.startswith(prefix + "."):
                    violations.append(f"{pyfile.name}: imports {module}")

    assert violations == [], (
        f"retrieval/stores must not import engine internals:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
