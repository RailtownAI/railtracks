from __future__ import annotations

from typing import Any, Awaitable, Callable, overload

from railtracks.llm.middleware import ModelMiddleware
from railtracks.llm.response import Response
from railtracks.utils.deprecation import warn_pending_change

from .post_llm import post_llm


@overload
def after_llm(
    fn: Callable[[Response], Response | Awaitable[Response]], /
) -> ModelMiddleware: ...


@overload
def after_llm(
    *, name: str | None = None
) -> Callable[
    [Callable[[Response], Response | Awaitable[Response]]], ModelMiddleware
]: ...


def after_llm(
    fn: Callable[[Response], Response | Awaitable[Response]] | None = None,
    /,
    *,
    name: str | None = None,
) -> Any:
    """Deprecated: Use ``rt.post_llm`` instead."""
    warn_pending_change(
        "rt.after_llm",
        change="is renamed",
        instead="rt.post_llm",
        detail="The function itself is unchanged.",
        stacklevel=2,
    )
    if fn is None:
        return post_llm(name=name)
    return post_llm(fn, name=name)
