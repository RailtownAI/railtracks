from typing import Awaitable, Callable

from pydantic import BaseModel

from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middlewares.core import wrap_node

from ..._types import LLM_CALL


def wrap_model(
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
    wrapped = wrap_node(fn)

    return wrapped
