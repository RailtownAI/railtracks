from pydantic import BaseModel

from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middleware.core import Middleware


class ModelMiddleware(
    Middleware[[MessageHistory, type[BaseModel] | None, list[Tool] | None], Response]
):
    """Middleware around each model call (``model_middleware=``), as built by
    ``pre_llm``/``post_llm``/``wrap_llm``."""
