from typing import Awaitable, Callable, Literal

from pydantic import BaseModel

from railtracks.llm.history import MessageHistory
from railtracks.llm.model import ModelBase
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool

LLM_CALL = Callable[
    [MessageHistory, type[BaseModel] | None, list[Tool] | None], Awaitable[Response]
]
ModelSource = ModelBase[Literal[False]] | Callable[[], ModelBase[Literal[False]]]
