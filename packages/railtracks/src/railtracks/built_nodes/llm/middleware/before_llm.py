from typing import Awaitable, Callable, TypeAlias, overload

from pydantic import BaseModel

from railtracks.built_nodes.llm.middleware.wrap_llm import wrap_llm
from railtracks.llm.history import MessageHistory
from railtracks.llm.tools.tool import Tool
from railtracks.utils.unpack import unpack_async_sync

from ..._types import LLM_CALL
from .core import ModelMiddleware

_BeforeLlmResult: TypeAlias = tuple[
    MessageHistory, type[BaseModel] | None, list[Tool] | None
]
_BeforeLlmFn: TypeAlias = Callable[
    [MessageHistory, type[BaseModel] | None, list[Tool] | None],
    _BeforeLlmResult | Awaitable[_BeforeLlmResult],
]


@overload
def before_llm(fn: _BeforeLlmFn, /, *, name: str | None = None) -> ModelMiddleware: ...


@overload
def before_llm(
    *, name: str | None = None
) -> Callable[[_BeforeLlmFn], ModelMiddleware]: ...


def before_llm(
    fn: _BeforeLlmFn | None = None,
    /,
    *,
    name: str | None = None,
) -> ModelMiddleware | Callable[[_BeforeLlmFn], ModelMiddleware]:
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

    def decorator(fn: _BeforeLlmFn) -> ModelMiddleware:
        @wrap_llm(name=name)
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
