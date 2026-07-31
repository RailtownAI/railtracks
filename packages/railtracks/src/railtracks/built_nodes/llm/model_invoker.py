from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, AsyncIterator, Awaitable, Callable

from pydantic import BaseModel

from railtracks.built_nodes._types import ModelSource
from railtracks.built_nodes.llm.middleware.core import ModelMiddleware
from railtracks.built_nodes.llm.middleware.wrap_llm import wrap_llm
from railtracks.built_nodes.llm.request_details import RequestDetails
from railtracks.context.central import get_stream_queue
from railtracks.exceptions.errors import LLMError
from railtracks.llm.history import MessageHistory
from railtracks.llm.model import ModelBase
from railtracks.llm.providers import TOOL_CALLING_STREAMING_BLACKLIST
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middleware.chain import MiddlewareChain
from railtracks.utils.logging import get_rt_logger

logger = get_rt_logger(__name__)


def _stream_queue_if_enabled(
    model: ModelBase, tools: list[Tool] | None
) -> asyncio.Queue[Any] | None:
    """
    Frame-level streaming decision for a single model call.

    Streaming is requested at the call site (`rt.astream`), which sets a per-call queue on the
    entry frame's context. This returns that queue only when streaming is genuinely available
    for this call, otherwise None (the call runs buffered). Tool-calling requests against
    blacklisted providers fall back to a buffered call (with a warning) instead of erroring.
    """
    queue = get_stream_queue()
    if queue is None:
        return None
    if (
        tools is not None
        and len(tools) > 0
        and model.model_provider() in TOOL_CALLING_STREAMING_BLACKLIST
    ):
        logger.warning(
            "Streaming is not supported with %s for tool calling; falling back to a "
            "buffered response.",
            model.model_provider(),
        )
        return None
    return queue


async def _drain_to_queue(
    model_stream: AsyncIterator[str | Response],
    queue: asyncio.Queue[Any],
) -> Response:
    """
    Consumes a model token stream, forwarding each `str` chunk onto the astream queue and
    returning the terminal `Response`.

    Mirrors the buffered call's fail-fast contract: if the stream ends without producing a
    `Response`, an `LLMError` is raised rather than returning a partial result.
    """
    final: Any = None
    async for item in model_stream:
        if isinstance(item, str):
            queue.put_nowait(("chunk", item))
        else:
            final = item

    if not isinstance(final, Response):
        raise LLMError(reason="The stream did not yield a final Response object.")

    return final


@wrap_llm
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
    ``(messages, schema, tools)`` and returns a :class:`Response`. Middleware wraps
    symmetrically (an earlier list entry is outer: it runs first going in and last
    coming out), so a ``@before_llm``/``@wrap_llm`` layer earlier in the list
    sees/transforms the request before one placed later, and sees the final
    ``Response`` after it on the way back out.

    Accepts a bare list of :class:`Middleware`. The caller's input is never mutated —
    a fresh copy is taken so system middleware (e.g. context injection) stays
    independent per node.
    """

    def __init__(
        self,
        model: ModelSource,
        middleware: list[ModelMiddleware] | None = None,
    ):
        self._get_model = model if callable(model) else lambda: model
        self._middleware = MiddlewareChain(middleware or [])

    @classmethod
    def create_with_llm_observe(
        cls, model: ModelSource, middleware: list[ModelMiddleware] | None = None
    ) -> ModelInvoker:
        """
        Creates a new :class:`ModelInvoker` with the given model and middleware, inserting the obersvation middleware as the last element run.
        """
        unwrapped_middleware = deepcopy(middleware) if middleware is not None else []
        return cls(model, [*unwrapped_middleware, _llm_observe])

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
            # Streaming path: consume the model stream here, forwarding each chunk directly to
            # the rt.astream handle's per-call queue, and hand the complete Response back
            # through the middleware chain — exit middleware (e.g. output guardrails) operates
            # on the buffered final response.
            stream_queue = _stream_queue_if_enabled(model, tools)
            if stream_queue is not None:
                if tools is not None and len(tools) > 0:
                    model_stream = model.astream_chat_with_tools(messages, tools=tools)
                elif schema is not None:
                    model_stream = model.astream_structured(messages, schema=schema)
                else:
                    model_stream = model.astream_chat(messages)

                # _drain_to_queue returns the complete Response (or raises LLMError if the
                # stream never produced one), mirroring the buffered branch below.
                return await _drain_to_queue(model_stream, stream_queue)

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

    def extend_middleware(self, *model_middleware: ModelMiddleware) -> ModelInvoker:
        """
        Returns a new :class:`ModelInvoker` with the given middleware appended to the
        existing middleware chain.
        """
        new_middleware_chain = deepcopy(self._middleware)

        for m in model_middleware:
            new_middleware_chain.add_middleware(m)

        return ModelInvoker(self._get_model, new_middleware_chain._middleware)
