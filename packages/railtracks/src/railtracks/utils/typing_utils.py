import inspect
import typing
import warnings
from typing import Any, Callable, Dict


def resolve_type_hints(func: Callable, signature: inspect.Signature) -> Dict[str, Any]:
    """
    Resolve type hints for PEP 563 (from __future__ import annotations).
    Only resolves type hints if any of the parameter annotations is a string.

    Args:
        func: The function to resolve type hints for.
        signature: The function's signature.

    Returns:
        A dictionary mapping parameter names to their resolved type hints.
    """
    resolved_types: Dict[str, Any] = {}

    # Check if any annotation is a string (PEP 563 style)
    if any(isinstance(p.annotation, str) for p in signature.parameters.values()):
        try:
            resolved_types = typing.get_type_hints(func, include_extras=True)
        except Exception as e:
            warnings.warn(
                f"Could not resolve type annotations for {func.__name__!r}: {e}. "
                "Unresolved parameters fall back to 'object'. Import the name at "
                "runtime or pass an explicit ToolManifest."
            )

    return resolved_types
