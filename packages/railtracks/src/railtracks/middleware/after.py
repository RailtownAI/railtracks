from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar, overload

from railtracks.utils.deprecation import warn_pending_change

from .core import Middleware
from .post import post_node

_R = TypeVar("_R")


@overload
def after_node(
    fn: Callable[[_R], Awaitable[_R]], /, *, name: str | None = None
) -> Middleware[..., _R]: ...


@overload
def after_node(
    *, name: str | None = None
) -> Callable[
    [Callable[[_R], Awaitable[_R]] | Callable[[_R], _R]], Middleware[..., _R]
]: ...


def after_node(
    fn: Callable[[_R], Awaitable[_R]] | Callable[[_R], _R] | None = None,
    /,
    *,
    name: str | None = None,
) -> Any:
    """Deprecated: Use ``rt.post_node`` instead."""
    warn_pending_change(
        "rt.after_node",
        change="is renamed",
        instead="rt.post_node",
        detail="The function itself is unchanged.",
    )
    if fn is None:
        return post_node(name=name)
    return post_node(fn, name=name)
