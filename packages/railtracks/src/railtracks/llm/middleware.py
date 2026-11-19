from pydantic import BaseModel

from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middleware.core import Middleware

ModelMiddleware = Middleware[
    [MessageHistory, type[BaseModel] | None, list[Tool] | None], Response
]


class ModelOnlyMiddleware(ModelMiddleware):
    """Model middleware that only works around a model call, as built by
    ``pre_llm``/``post_llm``/``wrap_llm``; lets a node without one reject it."""
