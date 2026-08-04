from typing import Awaitable, Callable

from pydantic import BaseModel

from railtracks.built_nodes._types import LLM_CALL
from railtracks.events.middleware import (
    MiddlewareModelOutputFailureEvent,
    MiddlewareModelOutputInvocationEvent,
    MiddlewareModelOutputResponseEvent,
)
from railtracks.events.send import pipe
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middleware.core import wrap_node
from railtracks.utils.unpack import unpack_async_sync


def after_llm(fn: Callable[[Response], Response | Awaitable[Response]]):
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

    @wrap_node
    async def wrapper(
        llm_call: LLM_CALL,
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ):
        try:
            response = await llm_call(message_history, schema, tools)
        except Exception as e:
            event = MiddlewareModelOutputFailureEvent(
                exception=e,
            )
            await pipe(event)
            raise e

        input_event = MiddlewareModelOutputInvocationEvent(
            response=response,
        )
        await pipe(input_event)

        response = await unpack_async_sync(fn(response))

        output_event = MiddlewareModelOutputResponseEvent(
            response=response,
        )

        await pipe(output_event)

        return response

    return wrapper
