from typing import Awaitable, Callable

from litellm import BaseModel
from railtracks.built_nodes.middlewares._llm_types import LLM_CALL
from railtracks.llm.history import MessageHistory
from railtracks.llm.tools.tool import Tool
from railtracks.llm.response import Response
from railtracks.middlewares.core import middleware
from railtracks.utils.unpack import unpack_async_sync


def after_llm(
    fn: Callable[[Response], Response | Awaitable[Response]]
):
    @middleware
    async def wrapper(
        llm_call: LLM_CALL,
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None
    ):
        response = await llm_call(message_history, schema, tools)
        return await unpack_async_sync(fn(response))
    
    return wrapper