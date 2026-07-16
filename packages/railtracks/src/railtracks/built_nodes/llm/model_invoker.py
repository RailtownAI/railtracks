from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Awaitable, Callable, Generator

from pydantic import BaseModel
from railtracks.built_nodes._types import ModelSource
from railtracks.built_nodes.llm.middleware.core import ModelMiddleware
from railtracks.built_nodes.llm.middleware.wrap_llm import wrap_llm
from railtracks.built_nodes.llm.request_details import RequestDetails
from railtracks.context.central import is_streaming_enabled
from railtracks.exceptions.errors import LLMError
from railtracks.interaction.broadcast_ import broadcast_stream
from railtracks.llm.history import MessageHistory
from railtracks.llm.model import ModelBase
from railtracks.llm.providers import TOOL_CALLING_STREAMING_BLACKLIST
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middleware.chain import MiddlewareChain
from railtracks.utils.logging import get_rt_logger

logger = get_rt_logger(__name__)


def _should_stream(model: ModelBase, tools: list[Tool] | None) -> bool:
    """
    Frame-level streaming decision for a single model call.

    Streaming is requested at the call site (`rt.astream` / `Flow.astream`)
    and is frame-local, so this returns True only for the entry frame of a streamed
    invocation. Tool-calling requests against blacklisted providers fall back to a buffered
    call (with a warning) instead of erroring.
    """
    if not is_streaming_enabled():
        return False
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
        return False
    return True


def _collect_legacy_stream(result: Response | Generator, messages: MessageHistory) -> Response:
    """
    Drains the sync generator returned by models constructed with the deprecated
    `stream=True` flag so buffered invocations still produce a complete `Response`.
    """
    if isinstance(result, Generator):
        final: Response | None = None
        for item in result:
            if isinstance(item, Response):
                final = item
        if final is None:
            raise LLMError(
                reason="The generator did not yield a final Response object",
                message_history=messages,
            )
        return final
    return result


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
    coming out), so a ``@before_model``/``@wrap_model`` layer earlier in the list
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
        stream_channel: str = "default",
    ):
        self._get_model = model if callable(model) else lambda: model
        self._middleware = MiddlewareChain(middleware or [])
        # the named channel this invoker's streamed chunks are broadcast on (see rt.broadcast)
        self._stream_channel = stream_channel

    @classmethod
    def create_with_llm_observe(
        cls,
        model: ModelSource,
        middleware: list[ModelMiddleware] | None = None,
        stream_channel: str = "default",
    ) -> ModelInvoker:
        """
        Creates a new :class:`ModelInvoker` with the given model and middleware, inserting the obersvation middleware as the last element run.
        """
        unwrapped_middleware = deepcopy(middleware) if middleware is not None else []
        return cls(
            model, [*unwrapped_middleware, _llm_observe], stream_channel=stream_channel
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
            # Streaming path: consume the model stream here, broadcasting each chunk to the
            # run's consumers (rt.astream / route() / broadcast_callback), and hand the complete Response
            # back through the middleware chain — exit middleware (e.g. output guardrails)
            # operates on the buffered final response.
            if _should_stream(model, tools):
                if tools is not None and len(tools) > 0:
                    model_stream = model.astream_chat_with_tools(messages, tools=tools)
                elif schema is not None:
                    model_stream = model.astream_structured(messages, schema=schema)
                else:
                    model_stream = model.astream_chat(messages)

                result = await broadcast_stream(
                    model_stream, channel=self._stream_channel
                )
                if not isinstance(result, Response):
                    raise LLMError(
                        reason="The model stream did not yield a final Response object.",
                        message_history=messages,
                    )
                return result

            if tools is not None and len(tools) > 0:
                buffered = await asyncio.to_thread(
                    model.chat_with_tools, messages, tools=tools
                )
            elif schema is not None:
                buffered = await asyncio.to_thread(
                    model.structured, messages, schema=schema
                )
            else:
                buffered = await asyncio.to_thread(model.chat, messages)

            return _collect_legacy_stream(buffered, messages)

        return await self._middleware.run(_core_llm_call, messages, schema, tools)

    def extend_middleware(self, *model_middleware: ModelMiddleware) -> ModelInvoker:
        """
        Returns a new :class:`ModelInvoker` with the given middleware appended to the
        existing middleware chain.
        """
        new_middleware_chain = deepcopy(self._middleware)

        for m in model_middleware:
            new_middleware_chain.add_middleware(m)

        return ModelInvoker(
            self._get_model,
            new_middleware_chain._middleware,
            stream_channel=self._stream_channel,
        )
