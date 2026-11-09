from __future__ import annotations

from copy import copy
from typing import Awaitable, Callable

from pydantic import BaseModel

from railtracks.llm.history import MessageHistory
from railtracks.llm.middleware import ModelOnlyMiddleware
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.prompts.prompt import inject_context


class ContextInjection(ModelOnlyMiddleware):
    """Inject ``rt.context`` values into prompt placeholders before each model call.

    Model-level middleware (``model_middleware=`` only). Fills ``{placeholder}``
    templates in the message history from the active session's context::

        import railtracks as rt
        from railtracks.prebuilt import middleware

        rt.agent_node(
            "Agent",
            llm=rt.llm.OpenAILLM(model_name="gpt-6-luna"),
            system_message="You are helping {user_name}.",
            model_middleware=[middleware.ContextInjection()],
        )

    List position matters: place it before (outside) any middleware that must see
    the injected prompt, e.g. an input guard listed after this entry sees the
    filled-in template.

    The placeholders are filled in a copy of the history, so the caller's messages
    keep their templates and each model call fills them exactly once.
    """

    def __init__(self):
        super().__init__(self._middleware_fn)

    async def _middleware_fn(
        self,
        call: Callable[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None],
            Awaitable[Response],
        ],
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ):
        filled = inject_context(MessageHistory([copy(m) for m in message_history]))
        return await call(filled, schema, tools)
