from __future__ import annotations

from typing import Any, Awaitable, Callable, overload

from pydantic import BaseModel

from railtracks.llm.history import MessageHistory
from railtracks.llm.middleware import ModelMiddleware
from railtracks.llm.tools.tool import Tool
from railtracks.utils.deprecation import warn_pending_change

from .pre_llm import pre_llm


@overload
def before_llm(
    fn: Callable[
        [MessageHistory, type[BaseModel] | None, list[Tool] | None],
        tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]
        | Awaitable[tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]],
    ],
    /,
    *,
    name: str | None = None,
) -> ModelMiddleware: ...


@overload
def before_llm(
    *, name: str | None = None
) -> Callable[
    [
        Callable[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None],
            tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]
            | Awaitable[
                tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]
            ],
        ]
    ],
    ModelMiddleware,
]: ...


def before_llm(
    fn: Callable[
        [MessageHistory, type[BaseModel] | None, list[Tool] | None],
        tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]
        | Awaitable[tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]],
    ]
    | None = None,
    /,
    *,
    name: str | None = None,
) -> Any:
    """Deprecated: Use ``rt.pre_llm`` instead."""
    warn_pending_change(
        "rt.before_llm",
        change="is renamed",
        instead="rt.pre_llm",
        detail="The function itself is unchanged.",
    )
    if fn is None:
        return pre_llm(name=name)
    return pre_llm(fn, name=name)
