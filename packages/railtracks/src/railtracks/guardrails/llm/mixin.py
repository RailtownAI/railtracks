"""
Mixin that implements LLMBase._pre_invoke and _post_invoke by running input/output guardrails.

Use by inheriting from this mixin and an LLM node class (e.g. TerminalLLM, StructuredLLM).
Set guardrails= when building the node. The mixin assumes self has message_hist, llm_model,
uuid, and that the context/result are MessageHistory and Response.
"""

from __future__ import annotations

from typing import Any, cast

from railtracks.llm.message import Message
from railtracks.llm.response import Response

from ..core import Guard, GuardrailBlockedError, GuardRunner
from ..core.decision import GuardrailAction
from ..core.event import LLMGuardrailEvent, LLMGuardrailPhase
from ..core.trace import GuardrailTrace


class LLMGuardrailsMixin:
    """
    Mixin for nodes that invoke an LLM. Overrides _pre_invoke and _post_invoke to run
    input and output guardrails. Set guardrails= when building the node.
    """

    guardrails: Guard | None = None

    def _append_guard_traces(self, traces: list[GuardrailTrace]) -> None:
        if not traces:
            return
        self._details["guard_details"].extend(traces)

    def _guardrail_agent_kind(self) -> str:
        cls_name = self.__class__.__name__.lower()
        if "structured" in cls_name:
            return "structured"
        if "terminal" in cls_name:
            return "terminal"
        return "llm"

    def _resolve_model_metadata(self) -> tuple[str | None, str | None]:
        model_name = getattr(self.llm_model, "model_name", None)
        if callable(model_name):
            model_name = model_name()
        model_provider = getattr(self.llm_model, "model_provider", None)
        if callable(model_provider):
            model_provider = model_provider()
        return (
            cast(str | None, model_name),
            str(model_provider) if model_provider is not None else None,
        )

    def _build_input_event(self, context: Any) -> LLMGuardrailEvent:
        """Build LLMGuardrailEvent for input phase from context (MessageHistory)."""
        model_name, model_provider = self._resolve_model_metadata()
        return LLMGuardrailEvent(
            phase=LLMGuardrailPhase.INPUT,
            messages=context,
            node_name=self.__class__.name(),
            node_uuid=self.uuid,
            model_name=model_name,
            model_provider=model_provider,
            tags={"agent_kind": self._guardrail_agent_kind()},
        )

    def _build_output_event(
        self, context: Any, assistant_message: Message
    ) -> LLMGuardrailEvent:
        """Build LLMGuardrailEvent for output phase: context is message history; assistant_message is this turn's output."""
        model_name, model_provider = self._resolve_model_metadata()
        return LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=context,
            output_message=assistant_message,
            node_name=self.__class__.name(),
            node_uuid=self.uuid,
            model_name=model_name,
            model_provider=model_provider,
            tags={"agent_kind": self._guardrail_agent_kind()},
        )

    def _pre_invoke(self, context: Any) -> Any:
        if self.guardrails is None or not self.guardrails.input:
            return context
        event = self._build_input_event(context)
        new_context, traces, decision = GuardRunner(self.guardrails).run_llm_input(
            event
        )
        self._append_guard_traces(traces)
        if decision is not None and decision.action == GuardrailAction.BLOCK:
            rail_name = traces[-1].rail_name if traces else None
            raise GuardrailBlockedError(
                rail_name=rail_name,
                reason=decision.reason,
                user_facing_message=decision.user_facing_message,
                traces=traces,
                meta=decision.meta,
            )

        return new_context

    def _post_invoke(self, context: Any, result: Any) -> Any:
        if self.guardrails is None or not self.guardrails.output:
            return result
        if not isinstance(result, Response):
            return result
        event = self._build_output_event(context, result.message)
        new_message, traces, decision = GuardRunner(self.guardrails).run_llm_output(
            event, result.message
        )
        self._append_guard_traces(traces)
        if decision is not None and decision.action == GuardrailAction.BLOCK:
            rail_name = traces[-1].rail_name if traces else None
            raise GuardrailBlockedError(
                rail_name=rail_name,
                reason=decision.reason,
                user_facing_message=decision.user_facing_message,
                traces=traces,
                meta=decision.meta,
            )

        return Response(message=new_message, message_info=result.message_info)
