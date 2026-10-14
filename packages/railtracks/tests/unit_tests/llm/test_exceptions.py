"""Layering tests for the boundary between the ``llm`` package and the node layer.

The ``llm`` package is self-contained: nothing inside it imports from the surrounding
``railtracks`` package, and it raises only its own error roots.
"""

import ast
import pathlib

import pytest
import railtracks.llm
from railtracks.exceptions import LLMError, NodeInvocationError
from railtracks.exceptions._base import RTError
from railtracks.llm._exceptions import ProviderError, RetryError
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


# The cross-dependencies that predate this change, tracked separately in #1096.
# Every other escape is a layering regression. Shrink this, never grow it.
KNOWN_ESCAPES = {
    "middleware.py": {"railtracks.middleware.core"},
    "models/cloud/azureai.py": {"railtracks.utils.deprecation"},
}


# =========== START layering tests ===========
@pytest.mark.parametrize(
    "module_path",
    sorted(LLM_PACKAGE_ROOT.rglob("*.py")),
    ids=lambda p: str(p.relative_to(LLM_PACKAGE_ROOT)).replace("\\", "/"),
)
def test_llm_package_does_not_import_upward(module_path: pathlib.Path):
    """No module in the llm package may import from the surrounding package.

    Checked on the whole import, not just error modules: reaching the framework's
    errors through an intermediary -- a validation or utils helper that raises an
    ``RTError`` of its own -- breaks the layering exactly the same way.
    """
    relative = str(module_path.relative_to(LLM_PACKAGE_ROOT)).replace("\\", "/")
    offenders = sorted(
        set(_escaping_imports(module_path)) - KNOWN_ESCAPES.get(relative, set())
    )
    assert offenders == [], (
        f"{relative} imports {offenders}; the llm package must not depend on the "
        "surrounding railtracks package. Errors it raises must be ProviderError or "
        "ToolCreationError types defined in railtracks.llm, translated at the "
        "llm_helpers boundary -- including errors raised on its behalf by a helper "
        "it calls"
    )


def test_known_escapes_are_all_still_real():
    """A stale allowlist entry silently widens the guard, so fail when one is fixed."""
    stale = [
        relative
        for relative, allowed in KNOWN_ESCAPES.items()
        if not (set(_escaping_imports(LLM_PACKAGE_ROOT / relative)) & allowed)
    ]
    assert stale == [], f"{stale} no longer escape; drop them from KNOWN_ESCAPES"


def _references_llmerror(path: pathlib.Path) -> bool:
    """True if `path` uses the name `LLMError` in code (prose mentions don't count)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "LLMError":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "LLMError":
            return True
        if isinstance(node, ast.ImportFrom) and any(
            a.name == "LLMError" for a in node.names
        ):
            return True
    return False


def test_llm_package_never_raises_llmerror():
    """`LLMError` describes a *node* terminating, which the llm package cannot know."""
    offenders = [
        str(p.relative_to(LLM_PACKAGE_ROOT)).replace("\\", "/")
        for p in LLM_PACKAGE_ROOT.rglob("*.py")
        if _references_llmerror(p)
    ]
    assert offenders == [], (
        f"{offenders} reference LLMError; the llm package should raise a ProviderError "
        "type and let llm_helpers translate it"
    )


# ========== END layering tests ==============


# =========== START hierarchy tests ===========
@pytest.mark.parametrize("error_cls", [ModelError, RetryError])
def test_provider_failures_root_at_providererror(error_cls):
    """Failures from talking to a model share one catchable root."""
    assert issubclass(error_cls, ProviderError)


def test_tool_creation_error_is_not_a_provider_error():
    """Disjoint roots, so `except ProviderError` cannot swallow a tool definition bug."""
    assert not issubclass(ToolCreationError, ProviderError)
    assert not issubclass(ProviderError, ToolCreationError)


@pytest.mark.parametrize("error_cls", [ModelError, RetryError, ToolCreationError])
def test_llm_package_errors_are_independent_of_rterror(error_cls):
    """Nothing the llm package raises may join the framework's hierarchy."""
    assert not issubclass(error_cls, RTError)


def test_llmerror_is_a_node_termination():
    """The two dispatch axes: *a node terminated*, and *the LLM caused it*."""
    assert issubclass(LLMError, NodeInvocationError)
    assert issubclass(LLMError, RTError)
    # It is a framework class, not one of the llm package's own errors.
    assert not issubclass(LLMError, ProviderError)


def test_llmerror_defaults_are_non_fatal():
    """Inheriting `fatal` from NodeInvocationError must not make LLM failures end runs."""
    err = LLMError("boom")
    assert err.fatal is False
    assert err.notes == []


# ========== END hierarchy tests ==============
