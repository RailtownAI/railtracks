import functools
from typing import Awaitable, Callable, overload

from pydantic import BaseModel

from railtracks.built_nodes._types import LLM_CALL
from railtracks.events.middleware import (
    MiddlewareModelOutputFailureEvent,
    MiddlewareModelOutputInvocationEvent,
    MiddlewareModelOutputResponseEvent,
)
from railtracks.events.send import emit
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.utils.unpack import unpack_async_sync

from .core import ModelMiddleware
from .wrap_llm import wrap_llm


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
) -> (
    ModelMiddleware
    | Callable[[Callable[[Response], Response | Awaitable[Response]]], ModelMiddleware]
):
    """
    A special decorator to create a middleware that runs after every successful call to the model.

    Example usage:
    ```python
    @after_llm
    async def my_middleware(response):
        # do something with the response
        return response
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
            response = await llm_call(message_history, schema, tools)

            invocation_event = MiddlewareModelOutputInvocationEvent(
                response=response,
            )
            await emit(invocation_event)

            try:
                response = await unpack_async_sync(fn(response))
            except Exception as e:
                failure_event = MiddlewareModelOutputFailureEvent.from_exception(e)
                await emit(failure_event)
                raise e

            response_event = MiddlewareModelOutputResponseEvent(
                response=response,
            )
            await emit(response_event)

            return response

        return wrapper

    if fn is None:
        return decorator
    return decorator(fn)
