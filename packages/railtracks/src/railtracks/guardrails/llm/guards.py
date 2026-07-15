from typing import Awaitable, Callable

from pydantic import BaseModel
from railtracks.context.central import get_parent_id, get_run_id, is_context_present
from railtracks.guardrails.core.decision import GuardrailAction, GuardrailDecision
from railtracks.guardrails.core.errors import GuardrailBlockedError
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.guardrails.llm.interfaces import InputGuard, OutputGuard
from railtracks.guardrails.core.runner import GuardRunner
from railtracks.guardrails.core.trace import GuardrailTrace
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.utils.logging.create import get_rt_logger

from railtracks.built_nodes.llm.middleware.core import ModelMiddleware

logger = get_rt_logger("guardrails")



class InputGuardrailMiddleware(ModelMiddleware, GuardMixIn):
    def __init__(self, guard_fn: InputGuard):
        super().__init__(fn=self._create_fn(guard_fn))

    @classmethod
    def _create_fn(
        cls,
        guard_fn: InputGuard,
    ):
        async def fn(
            call: Callable[
                [MessageHistory, type[BaseModel] | None, list[Tool] | None],
                Awaitable[Response],
            ],
            message_history: MessageHistory,
            schema: type[BaseModel] | None,
            tools: list[Tool] | None,
        ):
            message_history, schema, tools = cls._input_wrapper(
                guard_fn, message_history, schema, tools
            )
            return await call(message_history, schema, tools)

        return fn

    @classmethod
    def _input_wrapper(
        cls,
        guard_fn: InputGuard,
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ):
        node_uuid, run_id = cls._node_metadata()
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.INPUT,
            messages=message_history,
            node_uuid=node_uuid,
            run_id=run_id,
        )
        new_messages, traces, decision = cls._guard_runner.run_llm_input(
            guard_fn, event
        )
        cls._record_guard_traces(traces)
        cls._raise_if_blocked(decision, traces)

        return new_messages, schema, tools


class OutputGuardrailMiddleware(ModelMiddleware):
    def __init__(self, guard_fn: OutputGuard):
        super().__init__(fn=self._create_fn(guard_fn))

    @classmethod
    def _create_fn(
        cls,
        guard_fn: OutputGuard,
    ):
        async def fn(
            call: Callable[
                [MessageHistory, type[BaseModel] | None, list[Tool] | None],
                Awaitable[Response],
            ],
            message_history: MessageHistory,
            schema: type[BaseModel] | None,
            tools: list[Tool] | None,
        ):
            response = await call(message_history, schema, tools)
            return cls._output_wrapper(guard_fn, response)

        return fn

    @classmethod
    def _output_wrapper(
        cls,
        guard_fn: OutputGuard,
        result: Response,
    ):
        if cls._is_intermediate_tool_call(result):
            return result

        node_uuid, run_id = cls._node_metadata()
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([]),  # exit-gate seam carries no upstream history
            output_message=result.message,
            node_uuid=node_uuid,
            run_id=run_id,
        )
        new_message, traces, decision = cls._guard_runner.run_llm_output(
            guard_fn, event, result.message
        )
        cls._record_guard_traces(traces)
        cls._raise_if_blocked(decision, traces)

        if new_message is result.message:
            return result
        return Response(message=new_message, message_info=result.message_info)

    @staticmethod
    def _is_intermediate_tool_call(response: Response) -> bool:
        """A model round-trip is *intermediate* (not the final reply) when it requests tools.

        Mirrors ``process_message`` in ``llm_helpers`` (tool calls present => "Tool").
        """
        return len(response.message.tool_calls) > 0
