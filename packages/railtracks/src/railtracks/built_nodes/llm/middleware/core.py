from pydantic import BaseModel

from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middlewares.core import Middleware

ModelMiddleware = Middleware[
    [MessageHistory, type[BaseModel] | None, list[Tool] | None], Response
]
