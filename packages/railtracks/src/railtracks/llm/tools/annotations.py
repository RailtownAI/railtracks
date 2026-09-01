"""
Runtime resolution of function type annotations.

Annotations are strings whenever a module uses ``from __future__ import annotations``
(PEP 563). :func:`resolved_signature` manually parse them instead.
"""

import functools
import inspect
import warnings
from typing import Any, Callable, Dict, List, Mapping, Tuple

__all__ = ["resolved_signature", "resolve_annotation"]


def _annotation_namespaces(
    func: Callable[..., Any],
) -> Tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Return the ``(globalns, localns)`` used to evaluate ``func``'s annotations.

    Mirrors what :func:`typing.get_type_hints` uses: the globals of the module the
    function was defined in, plus the function's closure-free type params.

    Args:
        func: The callable whose annotations need a namespace.

    Returns:
        A ``(globals, locals)`` pair suitable for :func:`eval`.
    """
    underlying = inspect.unwrap(func)
    # partials, bound methods and class methods all hide the real function
    while isinstance(underlying, functools.partial):
        underlying = inspect.unwrap(underlying.func)
    # bound method
    underlying = getattr(underlying, "__func__", underlying)

    globalns: Mapping[str, Any] = getattr(underlying, "__globals__", {})
    # PEP 695 type parameters are only visible through the function object
    localns: Dict[str, Any] = {
        tp.__name__: tp for tp in getattr(underlying, "__type_params__", ())
    }
    return globalns, localns


def resolve_annotation(
    annotation: Any,
    globalns: Mapping[str, Any],
    localns: Mapping[str, Any],
) -> Any:
    """Evaluate a single annotation if it is still a string or a forward reference.

    Args:
        annotation: The raw annotation taken off an :class:`inspect.Parameter`.
        globalns: Global namespace to evaluate against.
        localns: Local namespace to evaluate against.

    Returns:
        The evaluated type; do not change if it is already a type or
        cannot be resolved.
    """
    if isinstance(annotation, str):
        expression = annotation
    elif hasattr(annotation, "__forward_arg__"):
        expression = annotation.__forward_arg__
    else:
        return annotation

    try:
        # typing.get_type_hints()'s exact behaviour
        return eval(expression, dict(globalns), dict(localns))  # noqa: S307
    except Exception:
        # A name that only exists under TYPE_CHECKING, or a genuinely bad
        # annotation. Neither should stop a tool from being built.
        return annotation


def resolved_signature(func: Callable[..., Any]) -> inspect.Signature:
    """Return ``func``'s signature with string (PEP 563) annotations evaluated.

    Unresolvable annotations are left as-is and reported through :mod:`warnings`
    rather than raised, so a single bad annotation cannot break tool creation.

    Args:
        func: The callable to inspect.

    Returns:
        An :class:`inspect.Signature` whose parameter annotations are real types
        wherever they could be resolved.

    Raises:
        ValueError: If ``func`` has no introspectable signature (e.g. some builtins).
    """
    signature = inspect.signature(func)

    if not any(
        isinstance(p.annotation, str) or hasattr(p.annotation, "__forward_arg__")
        for p in signature.parameters.values()
    ):
        # nothing deferred, so avoid touching namespaces entirely.
        return signature

    globalns, localns = _annotation_namespaces(func)

    unresolved: List[str] = []
    parameters = []
    for param in signature.parameters.values():
        resolved = resolve_annotation(param.annotation, globalns, localns)
        if resolved is param.annotation and isinstance(param.annotation, str):
            unresolved.append(param.name)
        parameters.append(param.replace(annotation=resolved))

    if unresolved:
        warnings.warn(
            f"Could not resolve type annotations for parameter(s) "
            f"{', '.join(unresolved)} of '{getattr(func, '__qualname__', func)}'. "
            "Their tool schema will fall back to a generic object type; consider "
            "importing the referenced names at runtime instead of only under "
            "TYPE_CHECKING.",
            UserWarning,
            stacklevel=3,
        )

    return signature.replace(parameters=parameters)
