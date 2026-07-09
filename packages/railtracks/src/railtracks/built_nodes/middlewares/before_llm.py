from typing import Awaitable, Callable

from pydantic import BaseModel
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middlewares.core import middleware
from railtracks.utils.unpack import unpack_async_sync

from ._llm_types import LLM_CALL


def before_llm(
    fn: Callable[[MessageHistory, type[BaseModel] | None, list[Tool] | None], tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None] | Awaitable[tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]]]
):
    @middleware
    async def wrapper(
        llm_call: LLM_CALL,
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None
    ):
        message_history, schema, tools = await unpack_async_sync(fn(message_history, schema, tools))
        return await llm_call(message_history, schema, tools)
    

    return wrapper