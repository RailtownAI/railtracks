from typing import Awaitable, Callable

from mypyc.build import emit_messages
from pydantic import BaseModel

from railtracks.events.middleware import (
    MiddlewareModelFailureEvent,
    MiddlewareModelInvocationEvent,
    MiddlewareModelResponseEvent,
)
from railtracks.events.send import pipe, emit
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middleware.core import wrap_node

from ..._types import LLM_CALL


def wrap_llm(
    fn: Callable[
        [LLM_CALL, MessageHistory, type[BaseModel] | None, list[Tool] | None],
        Awaitable[Response],
    ],
):
    """
    A special decorator to create a middleware wrapper that wraps every call to an llm

    Example usage:
    ```python
    @wrap_model
    async def my_middleware(llm_call, message_history, schema, tools):
        # do something with the inputs
        response = await llm_call(message_history, schema, tools)
        # do something with the response
        return response
    ```
    """

    @wrap_node
    async def _pipe_wrapped(
        llm_call: LLM_CALL,
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ):
        input_event = MiddlewareModelInvocationEvent(
            message_history=message_history,
            schema=schema,
            tools=tools,
        )
        await emit(input_event)

        try:
            response = await fn(llm_call, message_history, schema, tools)
        except Exception as e:
            event = MiddlewareModelFailureEvent.from_exception(e)
            await emit(event)
            raise e

        output_event = MiddlewareModelResponseEvent(
            response=response,
        )

        await emit(output_event)

        return response

    return _pipe_wrapped
