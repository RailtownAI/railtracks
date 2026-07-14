from typing import Awaitable, Callable

from pydantic import BaseModel

from railtracks.built_nodes.llm.middleware.wrap_model import wrap_model
from railtracks.llm.history import MessageHistory
from railtracks.llm.tools.tool import Tool
from railtracks.utils.unpack import unpack_async_sync

from ..._types import LLM_CALL


def before_model(
    fn: Callable[
        [MessageHistory, type[BaseModel] | None, list[Tool] | None],
        tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]
        | Awaitable[tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]],
    ],
):
    """
    A special decorator to create a middleware that maps the inputs to a new input before every call to a model

    Example usage:
    ```python
    @before_model
    async def my_middleware(message_history, schema, tools):
        # do something with the inputs
        return message_history, schema, tools
    ```
    """

    @wrap_model
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
