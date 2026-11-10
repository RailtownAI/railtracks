"""Layering tests for the boundary between ``railtracks.retrieval`` and the rest of
railtracks.

Retrieval runs outside a Flow as often as inside one, so it imports nothing from the
surrounding package except ``railtracks.exceptions`` and ``railtracks.observability``.
"""

import ast
import pathlib

import pytest
import railtracks.retrieval
from railtracks.retrieval._logging import get_logger
from railtracks.utils.logging.config import rt_logger_name

RETRIEVAL_ROOT = pathlib.Path(railtracks.retrieval.__file__).parent

ALLOWED_PREFIXES = (
    "railtracks.retrieval",
    "railtracks.exceptions",
    "railtracks.observability",
)

MODULES = sorted(RETRIEVAL_ROOT.rglob("*.py"))


def _module_id(path: pathlib.Path) -> str:
    return str(path.relative_to(RETRIEVAL_ROOT)).replace("\\", "/")


def _is_allowed(module: str) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in ALLOWED_PREFIXES
    )


def _escaping_imports(path: pathlib.Path) -> list[str]:
    """Every railtracks module outside the allowed set that ``path`` imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    depth_to_root = len(path.relative_to(RETRIEVAL_ROOT).parts)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            # a relative import that climbs above the retrieval package escapes it
            if node.level > depth_to_root:
                found.append("." * node.level + module)
            elif node.level == 0 and module.split(".")[0] == "railtracks":
                if not _is_allowed(module):
                    found.append(module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "railtracks" and not _is_allowed(
                    alias.name
                ):
                    found.append(alias.name)
    return found


@pytest.mark.parametrize("module_path", MODULES, ids=_module_id)
def test_retrieval_package_does_not_import_upward(module_path: pathlib.Path):
    offenders = _escaping_imports(module_path)
    assert offenders == [], (
        f"{_module_id(module_path)} imports {offenders}; retrieval may only import "
        f"{list(ALLOWED_PREFIXES)} from railtracks, spelled out in full (e.g. "
        "`from railtracks.exceptions import X`, not `from railtracks import "
        "exceptions`). Use railtracks.retrieval._logging.get_logger for loggers."
    )


def test_retrieval_loggers_hang_under_the_rt_logger():
    assert get_logger("embedding").name == f"{rt_logger_name}.retrieval.embedding"
