from typing import Awaitable, Callable, TypeAlias, overload

from pydantic import BaseModel

from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middleware.core import wrap_node

from ..._types import LLM_CALL
from .core import ModelMiddleware

_WrapLlmFn: TypeAlias = Callable[
    [LLM_CALL, MessageHistory, type[BaseModel] | None, list[Tool] | None],
    Awaitable[Response],
]


@overload
def wrap_llm(fn: _WrapLlmFn, /, *, name: str | None = None) -> ModelMiddleware: ...


@overload
def wrap_llm(*, name: str | None = None) -> Callable[[_WrapLlmFn], ModelMiddleware]: ...


def wrap_llm(
    fn: _WrapLlmFn | None = None,
    /,
    *,
    name: str | None = None,
) -> ModelMiddleware | Callable[[_WrapLlmFn], ModelMiddleware]:
    """
    A special decorator to create a middleware wrapper that wraps every call to an llm

    Example usage:
    ```python
    @wrap_llm
    async def my_middleware(llm_call, message_history, schema, tools):
        # do something with the inputs
        response = await llm_call(message_history, schema, tools)
        # do something with the response
        return response
    ```
    """

    def decorator(fn: _WrapLlmFn) -> ModelMiddleware:
        @wrap_node(name=name)
        async def wrapped(
            llm_call: LLM_CALL,
            message_history: MessageHistory,
            schema: type[BaseModel] | None,
            tools: list[Tool] | None,
        ):
            return await fn(llm_call, message_history, schema, tools)

        return wrapped

    if fn is None:
        return decorator
    return decorator(fn)
