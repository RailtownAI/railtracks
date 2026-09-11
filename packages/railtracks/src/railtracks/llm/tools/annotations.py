"""
Runtime resolution of function type annotations.

Annotations are strings whenever a module uses ``from __future__ import annotations``
(PEP 563). :func:`resolved_signature` evaluates them, including forward references
nested inside generics such as ``list["Payload"]``.
"""

import functools
import inspect
import types
import warnings
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Tuple,
    Union,
    get_args,
    get_origin,
)

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


def _deferred_expression(annotation: Any) -> Optional[str]:
    """Return the source text of ``annotation`` if it still needs evaluating.

    Args:
        annotation: Any annotation, at any nesting depth.

    Returns:
        The expression to evaluate, or ``None`` when the annotation is already a
        runtime object.
    """
    if isinstance(annotation, str):
        return annotation
    forward_arg = getattr(annotation, "__forward_arg__", None)
    return forward_arg if isinstance(forward_arg, str) else None


def _annotated_base(annotation: Any) -> Optional[Any]:
    """Return the type ``Annotated[...]`` wraps, or ``None`` for anything else.

    Args:
        annotation: The annotation to unwrap.

    Returns:
        The wrapped type, or ``None`` when ``annotation`` carries no metadata.
    """
    if hasattr(annotation, "__metadata__"):
        return getattr(annotation, "__origin__", None)
    return None


def _is_deferred(annotation: Any) -> bool:
    """Report whether ``annotation`` holds an unevaluated name anywhere inside it.

    Args:
        annotation: The annotation to scan.

    Returns:
        ``True`` if evaluating the annotation could change it.
    """
    if _deferred_expression(annotation) is not None:
        return True
    if get_origin(annotation) is Literal:
        # Literal's arguments are values, never types
        return False

    base = _annotated_base(annotation)
    if base is not None:
        return _is_deferred(base)

    for arg in get_args(annotation):
        # Callable[[int, str], bool] nests its parameter types in a list
        candidates = arg if isinstance(arg, list) else [arg]
        if any(_is_deferred(candidate) for candidate in candidates):
            return True
    return False


def _rebuild(annotation: Any, origin: Any, args: Tuple[Any, ...]) -> Any:
    """Reconstruct a parametrised generic with new arguments.

    Args:
        annotation: The original generic, used for its ``copy_with`` when available.
        origin: The generic's origin, as returned by :func:`typing.get_origin`.
        args: The replacement arguments.

    Returns:
        The rebuilt generic, or ``annotation`` unchanged if it cannot be rebuilt.
    """
    if origin is Union or origin is getattr(types, "UnionType", type(None)):
        # a union's origin is not subscriptable, so go through typing.Union
        return Union[args]

    copy_with = getattr(annotation, "copy_with", None)
    if copy_with is not None:
        try:
            return copy_with(args)
        except Exception:
            pass

    try:
        return origin[args]
    except Exception:
        return annotation


def _resolve(
    annotation: Any,
    globalns: Dict[str, Any],
    localns: Dict[str, Any],
    unresolved: List[str],
) -> Any:
    """Resolve ``annotation`` and every forward reference nested inside it.

    Args:
        annotation: The annotation to resolve.
        globalns: Global namespace to evaluate against.
        localns: Local namespace to evaluate against.
        unresolved: Accumulator for expressions that could not be evaluated.

    Returns:
        The resolved annotation, with any unevaluable part left as it was.
    """
    expression = _deferred_expression(annotation)
    if expression is not None:
        try:
            annotation = eval(expression, globalns, localns)  # noqa: S307
        except Exception:
            # A name that only exists under TYPE_CHECKING, or a genuinely bad
            # annotation. Neither should stop a tool from being built.
            unresolved.append(expression)
            return annotation

    if get_origin(annotation) is Literal:
        return annotation

    base = _annotated_base(annotation)
    if base is not None:
        resolved_base = _resolve(base, globalns, localns, unresolved)
        if resolved_base is base:
            return annotation
        return _rebuild(annotation, get_origin(annotation), (resolved_base,))

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is None or not args:
        return annotation

    changed = False
    resolved_args: List[Any] = []
    for arg in args:
        if isinstance(arg, list):
            # Callable's parameter list has to stay a list after resolution
            resolved_list = [_resolve(a, globalns, localns, unresolved) for a in arg]
            changed = changed or any(
                new is not old for new, old in zip(resolved_list, arg)
            )
            resolved_args.append(resolved_list)
            continue
        resolved_arg = _resolve(arg, globalns, localns, unresolved)
        changed = changed or resolved_arg is not arg
        resolved_args.append(resolved_arg)

    if not changed:
        return annotation
    return _rebuild(annotation, origin, tuple(resolved_args))


def resolve_annotation(
    annotation: Any,
    globalns: Mapping[str, Any],
    localns: Mapping[str, Any],
) -> Any:
    """Evaluate an annotation, including forward references nested inside generics.

    Args:
        annotation: The raw annotation taken off an :class:`inspect.Parameter`.
        globalns: Global namespace to evaluate against.
        localns: Local namespace to evaluate against.

    Returns:
        The evaluated type. Any part that cannot be resolved is left as it was, so
        one bad name degrades a single branch of the schema rather than all of it.
    """
    return _resolve(annotation, dict(globalns), dict(localns), [])


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

    if not any(_is_deferred(p.annotation) for p in signature.parameters.values()):
        # nothing deferred, so avoid touching namespaces entirely.
        return signature

    raw_globalns, raw_localns = _annotation_namespaces(func)
    globalns, localns = dict(raw_globalns), dict(raw_localns)

    failures: Dict[str, List[str]] = {}
    parameters = []
    for param in signature.parameters.values():
        unresolved: List[str] = []
        resolved = _resolve(param.annotation, globalns, localns, unresolved)
        if unresolved:
            failures[param.name] = unresolved
        parameters.append(param.replace(annotation=resolved))

    if failures:
        detail = ", ".join(
            f"{name} ({', '.join(names)})" for name, names in failures.items()
        )
        warnings.warn(
            f"Could not resolve type annotations for parameter(s) {detail} of "
            f"'{getattr(func, '__qualname__', func)}'. Their tool schema will fall "
            "back to a generic object type; consider importing the referenced names "
            "at runtime instead of only under TYPE_CHECKING.",
            UserWarning,
            stacklevel=3,
        )

    return signature.replace(parameters=parameters)
