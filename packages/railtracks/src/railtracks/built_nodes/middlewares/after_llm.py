from typing import Awaitable, Callable

from litellm import BaseModel

from railtracks.built_nodes._types import LLM_CALL
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middlewares.core import wrap_node
from railtracks.utils.unpack import unpack_async_sync


def after_model(fn: Callable[[Response], Response | Awaitable[Response]]):
    """
    A special decorator to create a middleware that runs after every successful call to the model.
    """
    @wrap_node
    async def wrapper(
        llm_call: LLM_CALL,
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ):
        response = await llm_call(message_history, schema, tools)
        return await unpack_async_sync(fn(response))

    return wrapper
