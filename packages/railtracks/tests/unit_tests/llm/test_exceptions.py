"""Layering tests for the exceptions raised out of the ``llm`` package.

The ``llm`` package is meant to stand on its own, so nothing inside it may import from
the surrounding ``railtracks`` package. ``LLMError`` lives here for that reason and is
re-exported by ``railtracks.exceptions`` for backwards compatibility.
"""

import ast
import pathlib

import pytest
import railtracks.llm
from railtracks.exceptions import LLMError as PublicLLMError
from railtracks.exceptions._base import RTError
from railtracks.llm._exceptions import LLMError, RetryError, RTLLMError
from railtracks.llm.tools.tool import ToolCreationError

LLM_PACKAGE_ROOT = pathlib.Path(railtracks.llm.__file__).parent


def _railtracks_imports(path: pathlib.Path) -> list[str]:
    """Every module inside ``railtracks`` (but outside ``llm``) that ``path`` imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    depth_to_llm_root = len(path.relative_to(LLM_PACKAGE_ROOT).parts)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # A relative import that climbs above the llm package root escapes it.
            if node.level > depth_to_llm_root:
                found.append("." * node.level + (node.module or ""))
            elif node.level == 0 and (node.module or "").startswith("railtracks."):
                if not (node.module or "").startswith("railtracks.llm"):
                    found.append(node.module or "")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("railtracks.") and not alias.name.startswith(
                    "railtracks.llm"
                ):
                    found.append(alias.name)
    return found


# =========== START layering tests ===========
@pytest.mark.parametrize(
    "module_path",
    sorted(LLM_PACKAGE_ROOT.rglob("*.py")),
    ids=lambda p: str(p.relative_to(LLM_PACKAGE_ROOT)).replace("\\", "/"),
)
def test_llm_package_does_not_import_railtracks_errors(module_path: pathlib.Path):
    """No module in the llm package may reach into railtracks' error definitions."""
    offenders = [
        imported
        for imported in _railtracks_imports(module_path)
        if "exceptions" in imported
    ]
    assert offenders == [], (
        f"{module_path.relative_to(LLM_PACKAGE_ROOT)} imports {offenders}; "
        "errors raised from the llm package must be defined in railtracks.llm._exceptions"
    )


# ========== END layering tests ==============


# =========== START LLMError placement tests ===========
def test_public_llmerror_is_the_llm_package_class():
    """`railtracks.exceptions.LLMError` must stay the exact class the llm package raises."""
    assert PublicLLMError is LLMError


@pytest.mark.parametrize("error_cls", [LLMError, RetryError, ToolCreationError])
def test_llm_errors_share_both_bases(error_cls):
    """Moving LLMError must not drop it out of the framework-wide `RTError` hierarchy."""
    assert issubclass(error_cls, RTLLMError)
    assert issubclass(error_cls, RTError)


# ========== END LLMError placement tests ==============
