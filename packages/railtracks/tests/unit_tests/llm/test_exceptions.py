"""Layering tests for the boundary between the ``llm`` package and the node layer.

The ``llm`` package is self-contained: nothing inside it imports from the surrounding
``railtracks`` package, and it raises only ``RTLLMError`` types. It knows nothing about
nodes, so ``LLMError`` -- which means "a node terminated because the LLM failed" -- is a
framework class, produced by the single translation point in
``railtracks.built_nodes.llm.llm_helpers``.
"""

import ast
import pathlib
import re

import pytest
import railtracks.llm
from railtracks.exceptions import LLMError, NodeInvocationError
from railtracks.exceptions._base import RTError
from railtracks.llm._exceptions import RetryError, RTLLMError
from railtracks.llm.models._model_exception_base import ModelError
from railtracks.llm.tools.tool import ToolCreationError

LLM_PACKAGE_ROOT = pathlib.Path(railtracks.llm.__file__).parent


def _escaping_imports(path: pathlib.Path) -> list[str]:
    """Every module outside the ``llm`` package that ``path`` imports."""
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
    """No module in the llm package may reach into railtracks' error definitions.

    This is the regression guard for the cross-dependency this package was untangled
    from; `railtracks.exceptions` is the one that must never come back.
    """
    offenders = [
        imported
        for imported in _escaping_imports(module_path)
        if "exceptions" in imported
    ]
    assert offenders == [], (
        f"{module_path.relative_to(LLM_PACKAGE_ROOT)} imports {offenders}; "
        "errors raised from the llm package must be RTLLMError types defined in "
        "railtracks.llm, and translated at the llm_helpers boundary instead"
    )


def test_llm_package_never_raises_llmerror():
    """`LLMError` describes a *node* terminating, which the llm package cannot know."""
    # Negative lookbehind so this does not match the package's own `RTLLMError`.
    bare_llmerror = re.compile(r"(?<![A-Za-z0-9_])LLMError")
    offenders = [
        str(p.relative_to(LLM_PACKAGE_ROOT)).replace("\\", "/")
        for p in LLM_PACKAGE_ROOT.rglob("*.py")
        if bare_llmerror.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == [], (
        f"{offenders} reference LLMError; the llm package should raise an RTLLMError "
        "type and let llm_helpers translate it"
    )


# ========== END layering tests ==============


# =========== START hierarchy tests ===========
@pytest.mark.parametrize("error_cls", [ModelError, RetryError, ToolCreationError])
def test_llm_package_errors_root_at_rtllmerror(error_cls):
    """Everything the llm package raises is catchable from its own public root."""
    assert issubclass(error_cls, RTLLMError)
    assert not issubclass(error_cls, RTError)


def test_llmerror_is_a_node_termination():
    """The two dispatch axes: *a node terminated*, and *the LLM caused it*."""
    assert issubclass(LLMError, NodeInvocationError)
    assert issubclass(LLMError, RTError)
    # It is a framework class, not one of the llm package's own errors.
    assert not issubclass(LLMError, RTLLMError)


def test_llmerror_defaults_are_non_fatal():
    """Inheriting `fatal` from NodeInvocationError must not make LLM failures end runs."""
    err = LLMError("boom")
    assert err.fatal is False
    assert err.notes == []


# ========== END hierarchy tests ==============
