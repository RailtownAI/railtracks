import asyncio
from copy import deepcopy
from typing import Awaitable, Callable

from pydantic import BaseModel
from railtracks.built_nodes._types import ModelSource
from railtracks.built_nodes.llm.request_details import RequestDetails
from railtracks.built_nodes.middlewares.core import ModelMiddleware
from railtracks.built_nodes.middlewares.wrap_model import wrap_model
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middlewares.chain import MiddlewareChain


@wrap_model
async def _llm_observe(
        call: Callable[
            [MessageHistory, type[BaseModel] | None, list[Tool] | None],
            Awaitable[Response],
        ],
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ) -> Response:
        prev_message_history = deepcopy(message_history)
        response: Response = await call(message_history, schema, tools)
        _ = RequestDetails(
            message_input=prev_message_history,
            output=response.message,
            model_name=response.message_info.model_name,
            model_provider=None,  # TODO: implement parsing logic here
            input_tokens=response.message_info.input_tokens,
            output_tokens=response.message_info.output_tokens,
            total_cost=response.message_info.total_cost,
            system_fingerprint=response.message_info.system_fingerprint,
            latency=response.message_info.latency,
        )
        return response

class ModelInvoker:
    """
    Coordinates a single LLM model call through a :class:`MiddlewareChain`.

    The middleware operates around the *raw* model call, once per model
    round-trip (i.e. inside the tool-calling loop). The core callable takes
    ``(messages, schema, tools)`` and returns a :class:`Response`::

        middleware
        └── entry gateways   (transform messages / schema / tools)
            └── inner_middleware
                └── model.chat / structured / chat_with_tools
            └── (unwind)
        └── exit gateways    (transform the Response)
        └── (unwind)

    Accepts a :class:`MiddlewareChain` or a bare list of ``Middleware`` / ``Gate``
    (see :meth:`MiddlewareChain.coerce`). The caller's input is never mutated — a
    fresh copy is taken so system gateways (e.g. context injection) stay
    independent per node.
    """

    

    def __init__(
        self,
        model: ModelSource,
        middleware: list[ModelMiddleware] | None = None,
    ):
        self._get_model = model if callable(model) else lambda: model
        unwrapped_middleware = deepcopy(middleware) if middleware is not None else []
        self._middleware = MiddlewareChain(
            [
                _llm_observe,
                *unwrapped_middleware,
            ]
        )

    async def invoke(
        self,
        messages: MessageHistory,
        *,
        schema: type[BaseModel] | None = None,
        tools: list[Tool] | None = None,
    ) -> Response:
        model = self._get_model()

        async def _core_llm_call(
            messages: MessageHistory,
            schema: type[BaseModel] | None,
            tools: list[Tool] | None,
        ) -> Response:
            if tools is not None and len(tools) > 0:
                return await asyncio.to_thread(
                    model.chat_with_tools, messages, tools=tools
                )
            elif schema is not None:
                return await asyncio.to_thread(
                    model.structured, messages, schema=schema
                )
            else:
                return await asyncio.to_thread(model.chat, messages)

        return await self._middleware.run(_core_llm_call, messages, schema, tools)
