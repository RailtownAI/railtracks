import functools
from typing import Awaitable, Callable, overload

from pydantic import BaseModel

from railtracks.built_nodes.llm.middleware.wrap_llm import wrap_llm
from railtracks.events.middleware import (
    MiddlewareModelInputInvocationEvent,
    MiddlewareModelInputResponseEvent,
)
from railtracks.events.send import emit
from railtracks.llm.history import MessageHistory
from railtracks.llm.tools.tool import Tool
from railtracks.utils.unpack import unpack_async_sync

from ..._types import LLM_CALL
from .core import ModelMiddleware


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
) -> (
    ModelMiddleware
    | Callable[
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
    ]
):
    """
    A special decorator to create a middleware that maps the inputs to a new input before every call to a model

    Example usage:
    ```python
    @before_llm
    async def my_middleware(message_history, schema, tools):
        # do something with the inputs
        return message_history, schema, tools
    ```
    """

    def decorator(fn):
        @wrap_llm(name=name)
        @functools.wraps(fn)
        async def wrapper(
            llm_call: LLM_CALL,
            message_history: MessageHistory,
            schema: type[BaseModel] | None,
            tools: list[Tool] | None,
        ):
            message_history, schema, tools = await unpack_async_sync(
                fn(message_history, schema, tools)
            )
            return await llm_call(message_history, schema, tools)

        return wrapper

    if fn is None:
        return decorator
    return decorator(fn)
