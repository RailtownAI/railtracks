from typing import Awaitable, Callable

from pydantic import BaseModel
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middlewares.core import middleware


from ._llm_types import LLM_CALL


def middleware_llm(
    fn: Callable[[LLM_CALL, MessageHistory, type[BaseModel] | None, list[Tool] | None], Awaitable[Response]],
):
    middleware_fn = middleware(fn)

    return middleware_fn
    