"""Layering tests for the boundary between ``classifiers`` and the rest of railtracks.

Like ``llm`` (see ``tests/unit_tests/llm/test_exceptions.py``), the ``classifiers``
package is self-contained: it imports nothing from the surrounding ``railtracks``
package except ``railtracks.llm.retries``, and it raises only its own error roots.
"""

import ast
import pathlib

import pytest
import railtracks.classifiers
from railtracks.classifiers import (
    ClassifierAuthenticationError,
    ClassifierConnectionError,
    ClassifierError,
    ClassifierRateLimitError,
    ClassifierRequestError,
    ClassifierResponseError,
    ClassifierServerError,
    ClassifierTimeoutError,
    SchemaDefinitionError,
)
from railtracks.exceptions._base import RTError

CLASSIFIERS_ROOT = pathlib.Path(railtracks.classifiers.__file__).parent

# The one sideways dependency: retry strategies are shared with chat models.
ALLOWED_PREFIXES = ("railtracks.classifiers", "railtracks.llm.retries")

MODULES = sorted(CLASSIFIERS_ROOT.rglob("*.py"))


def _module_id(path: pathlib.Path) -> str:
    return str(path.relative_to(CLASSIFIERS_ROOT)).replace("\\", "/")


def _escaping_imports(path: pathlib.Path) -> list[str]:
    """Every module outside the allowed set that ``path`` imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    depth_to_root = len(path.relative_to(CLASSIFIERS_ROOT).parts)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            # a relative import that climbs above the classifiers package escapes it
            if node.level > depth_to_root:
                found.append("." * node.level + module)
            elif node.level == 0 and module.startswith("railtracks"):
                if not module.startswith(ALLOWED_PREFIXES):
                    found.append(module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("railtracks") and not alias.name.startswith(
                    ALLOWED_PREFIXES
                ):
                    found.append(alias.name)
    return found


@pytest.mark.parametrize("module_path", MODULES, ids=_module_id)
def test_classifiers_package_does_not_import_upward(module_path: pathlib.Path):
    offenders = _escaping_imports(module_path)
    assert offenders == [], (
        f"{_module_id(module_path)} imports {offenders}; classifiers may only import "
        f"{list(ALLOWED_PREFIXES)} from railtracks. Errors it raises must be "
        "ClassifierError or SchemaDefinitionError, translated at the decision node."
    )


def _rterror_names() -> set[str]:
    names: set[str] = set()
    pending: list[type] = [RTError]
    while pending:
        cls = pending.pop()
        names.add(cls.__name__)
        pending.extend(cls.__subclasses__())
    return names


def _raised_names(path: pathlib.Path) -> set[str]:
    """Names of the exception classes ``path`` raises (``raise X(...)``/``raise X``)."""
    raised: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        if isinstance(target, ast.Name):
            raised.add(target.id)
        elif isinstance(target, ast.Attribute):
            raised.add(target.attr)
    return raised


@pytest.mark.parametrize("module_path", MODULES, ids=_module_id)
def test_classifiers_package_never_raises_rterror(module_path: pathlib.Path):
    offenders = _raised_names(module_path) & _rterror_names()
    assert offenders == set(), (
        f"{_module_id(module_path)} raises {sorted(offenders)}; classifiers raise "
        "ClassifierError/SchemaDefinitionError and the invoker translates them"
    )


@pytest.mark.parametrize(
    "error_cls",
    [
        ClassifierError,
        ClassifierTimeoutError,
        ClassifierConnectionError,
        ClassifierRateLimitError,
        ClassifierServerError,
        ClassifierAuthenticationError,
        ClassifierRequestError,
        ClassifierResponseError,
        SchemaDefinitionError,
    ],
)
def test_classifier_errors_are_independent_of_rterror(error_cls):
    assert not issubclass(error_cls, RTError)


def test_error_roots_are_disjoint():
    """`except ClassifierError` must not swallow a schema definition bug."""
    assert not issubclass(SchemaDefinitionError, ClassifierError)
    assert not issubclass(ClassifierError, SchemaDefinitionError)
