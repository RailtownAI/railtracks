from typing import Awaitable, Callable

from pydantic import BaseModel

from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middlewares.core import wrap_node

from ._llm_types import LLM_CALL


def wrap_model(
    fn: Callable[
        [LLM_CALL, MessageHistory, type[BaseModel] | None, list[Tool] | None],
        Awaitable[Response],
    ],
):
    wrapped = wrap_node(fn)

    return wrapped
