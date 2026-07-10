"""Middleware gates that run the guardrails core around the raw model call.

These adapters let ``agent_node(..., guardrails=Guard(...))`` attach guardrails as
**system gates on the model-level middleware** (`ModelInvoker`).
They translate between the runner's ``(value, traces, decision)``
triple and the middleware transform contract (transform-or-raise):

- :func:`guardrail_input_gate`: an **entry gate**. Register with ``position="after"`` so
  it is the last gate before the model call (sees the fully assembled, injected,
  user-transformed prompt). Runs the input rails on the message history.
- :func:`guardrail_output_gate`: an **exit gate** (register as sys-exit, the last word).
  Runs the output rails on the final assistant reply; intermediate tool-call turns pass
  through untouched.

The guardrails core (:class:`GuardRunner`, the built-in guards, decisions, traces) is
reused unchanged; only the seam moves off the old ``LLMGuardrailsMixin``.
"""

from __future__ import annotations

from pydantic import BaseModel

from railtracks.built_nodes.middlewares import after_llm, before_llm
from railtracks.context.central import (
    get_parent_id,
    get_run_id,
    is_context_present,
)
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.utils.logging import get_rt_logger

from ..core import Guard, GuardrailBlockedError, GuardRunner
from ..core.decision import GuardrailAction, GuardrailDecision
from ..core.event import LLMGuardrailEvent, LLMGuardrailPhase
from ..core.trace import GuardrailTrace

logger = get_rt_logger("guardrails")


def _node_metadata() -> tuple[str | None, str | None]:
    """``(node_uuid, run_id)`` for event observability.

    Returns ``(None, None)`` when no run context is active — the gate logic never
    depends on this metadata, so it must not raise just to populate it.
    """
    if not is_context_present():
        return None, None
    return get_parent_id(), get_run_id()


def _record_guard_traces(traces: list[GuardrailTrace]) -> None:
    """The single sink for guardrail traces.

    TODO: Determine the correct home for observability traces. For now, just log them at debug level.
    """
    for t in traces:
        logger.debug("guardrail trace: %s", t)


def _is_intermediate_tool_call(response: Response) -> bool:
    """A model round-trip is *intermediate* (not the final reply) when it requests tools.

    Mirrors ``process_message`` in ``llm_helpers`` (tool calls present => "Tool").
    """
    return len(response.message.tool_calls) > 0


def _raise_if_blocked(
    decision: GuardrailDecision | None, traces: list[GuardrailTrace]
) -> None:
    """Raise :class:`GuardrailBlockedError` when a rail returned ``BLOCK``."""
    if decision is not None and decision.action == GuardrailAction.BLOCK:
        rail_name = traces[-1].rail_name if traces else None
        raise GuardrailBlockedError(
            rail_name=rail_name,
            reason=decision.reason,
            user_facing_message=decision.user_facing_message,
            traces=traces,
            meta=decision.meta,
        )


def guardrail_input_middleware(guard: Guard):
    """Build an entry gate that runs ``guard.input`` on the message history.

    Register on the model middleware with ``position="after"`` so it runs after any user
    entry gates; the last transform before the model call. On ``BLOCK`` it raises
    :class:`GuardrailBlockedError`; on ``TRANSFORM`` it forwards the rewritten history;
    on ``ALLOW`` it passes through unchanged.
    """

    @before_llm
    async def _input_gate(
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ):
        if not guard.input:
            return message_history, schema, tools

        node_uuid, run_id = _node_metadata()
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.INPUT,
            messages=message_history,
            node_uuid=node_uuid,
            run_id=run_id,
        )
        new_messages, traces, decision = GuardRunner(guard).run_llm_input(event)
        _record_guard_traces(traces)
        _raise_if_blocked(decision, traces)

        return new_messages, schema, tools

    return _input_gate


def guardrail_output_middleware(guard: Guard):
    """Build an exit gate that runs ``guard.output`` on the final model ``Response``.

    Register on the model middleware as a sys exit gate (the last word on the response).
    Intermediate tool-call turns pass through untouched, so output rails fire only on the
    final reply. On ``BLOCK`` it raises; on ``TRANSFORM`` it returns a rewritten
    ``Response``; on ``ALLOW`` it passes through unchanged.
    """

    @after_llm
    async def _output_gate(
        result: Response,
    ):
        if not guard.output:
            return result
        if _is_intermediate_tool_call(result):
            return result

        node_uuid, run_id = _node_metadata()
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([]),  # exit-gate seam carries no upstream history
            output_message=result.message,
            node_uuid=node_uuid,
            run_id=run_id,
        )
        new_message, traces, decision = GuardRunner(guard).run_llm_output(
            event, result.message
        )
        _record_guard_traces(traces)
        _raise_if_blocked(decision, traces)

        if new_message is result.message:
            return result
        return Response(message=new_message, message_info=result.message_info)

    return _output_gate
