from typing import Awaitable, Callable

from pydantic import BaseModel

from railtracks.built_nodes.middlewares.wrap_model import wrap_model
from railtracks.llm.history import MessageHistory
from railtracks.llm.tools.tool import Tool
from railtracks.utils.unpack import unpack_async_sync

from .._types import LLM_CALL


def before_model(
    fn: Callable[
        [MessageHistory, type[BaseModel] | None, list[Tool] | None],
        tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]
        | Awaitable[tuple[MessageHistory, type[BaseModel] | None, list[Tool] | None]],
    ],
):
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
