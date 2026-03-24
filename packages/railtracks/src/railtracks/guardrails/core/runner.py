from __future__ import annotations

from typing import Callable, Iterable, Literal, TypeVar, cast

from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message

from .config import Guard
from .decision import GuardrailAction, GuardrailDecision
from .event import LLMGuardrailEvent, LLMGuardrailPhase
from .interfaces import LLMGuardrail
from .trace import GuardrailTrace

_TValue = TypeVar("_TValue")


def _rail_name(rail: LLMGuardrail) -> str:
    name = getattr(rail, "name", None)
    if isinstance(name, str) and name.strip():
        return name
    return rail.__class__.__name__


def _trace_from_decision(
    *,
    rail: LLMGuardrail,
    phase: LLMGuardrailPhase,
    decision: GuardrailDecision,
) -> GuardrailTrace:
    return GuardrailTrace(
        rail_name=_rail_name(rail),
        phase=phase.value,
        action=decision.action.value,
        reason=decision.reason,
        meta=decision.meta,
    )


def _trace_for_exception(
    *,
    rail: LLMGuardrail,
    phase: LLMGuardrailPhase,
    exc: Exception,
) -> GuardrailTrace:
    return GuardrailTrace(
        rail_name=_rail_name(rail),
        phase=phase.value,
        action="error",
        reason="Guardrail raised exception",
        meta={
            "exception_type": exc.__class__.__name__,
            "exception_message": str(exc),
        },
    )


class GuardRunner:
    def __init__(self, guard: Guard):
        self.guard = guard

    def _sync_event_after_transform(
        self,
        phase: LLMGuardrailPhase,
        event: LLMGuardrailEvent,
        value: _TValue,
    ) -> LLMGuardrailEvent:
        if phase == LLMGuardrailPhase.INPUT:
            return event.model_copy(update={"messages": cast(MessageHistory, value)})
        return event.model_copy(update={"output_message": cast(Message, value)})

    def _handle_rail_exception(
        self,
        *,
        rail: LLMGuardrail,
        phase: LLMGuardrailPhase,
        exc: Exception,
        traces: list[GuardrailTrace],
        value: _TValue,
        reason_prefix: str,
    ) -> tuple[Literal["continue"], _TValue] | tuple[Literal["stop"], _TValue, GuardrailDecision]:
        traces.append(_trace_for_exception(rail=rail, phase=phase, exc=exc))
        if self.guard.fail_open:
            return ("continue", value)
        block = GuardrailDecision.block(
            reason=f"{reason_prefix}: {_rail_name(rail)}",
            user_facing_message="Request blocked by guardrails.",
            meta={
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc),
            },
        )
        return ("stop", value, block)

    def _dispatch_non_allow_decision(
        self,
        *,
        rail: LLMGuardrail,
        phase: LLMGuardrailPhase,
        event: LLMGuardrailEvent,
        value: _TValue,
        decision: GuardrailDecision,
        traces: list[GuardrailTrace],
        apply_transform: Callable[[_TValue, GuardrailDecision], _TValue],
    ) -> (
        tuple[Literal["continue"], _TValue, LLMGuardrailEvent]
        | tuple[Literal["stop"], _TValue, GuardrailDecision]
    ):
        if decision.action == GuardrailAction.TRANSFORM:
            try:
                value = apply_transform(value, decision)
                event = self._sync_event_after_transform(phase, event, value)
            except Exception as e:
                outcome = self._handle_rail_exception(
                    rail=rail,
                    phase=phase,
                    exc=e,
                    traces=traces,
                    value=value,
                    reason_prefix="Guardrail transform failed",
                )
                if outcome[0] == "continue":
                    return ("continue", value, event)
                return ("stop", outcome[1], outcome[2])
            return ("continue", value, event)

        if decision.action == GuardrailAction.BLOCK:
            return ("stop", value, decision)

        traces.append(
            GuardrailTrace(
                rail_name=_rail_name(rail),
                phase=phase.value,
                action="error",
                reason="Unknown guardrail action",
                meta={"action": str(decision.action)},
            )
        )
        if self.guard.fail_open:
            return ("continue", value, event)
        block = GuardrailDecision.block(
            reason=f"Unknown guardrail action from {_rail_name(rail)}",
            user_facing_message="Request blocked by guardrails.",
        )
        return ("stop", value, block)

    def _eval_one_rail(
        self,
        rail: LLMGuardrail,
        phase: LLMGuardrailPhase,
        event: LLMGuardrailEvent,
        value: _TValue,
        traces: list[GuardrailTrace],
        apply_transform: Callable[[_TValue, GuardrailDecision], _TValue],
    ) -> tuple[Literal["continue"], _TValue, LLMGuardrailEvent] | tuple[
        Literal["stop"], _TValue, GuardrailDecision
    ]:
        try:
            decision = rail(event)
            if not isinstance(decision, GuardrailDecision):
                raise TypeError(
                    f"Guardrail {_rail_name(rail)!r} returned {type(decision).__name__}, expected GuardrailDecision."
                )
        except Exception as e:
            outcome = self._handle_rail_exception(
                rail=rail,
                phase=phase,
                exc=e,
                traces=traces,
                value=value,
                reason_prefix="Guardrail raised exception",
            )
            if outcome[0] == "continue":
                return ("continue", value, event)
            return ("stop", outcome[1], outcome[2])

        traces.append(
            _trace_from_decision(rail=rail, phase=phase, decision=decision)
        )

        if decision.action == GuardrailAction.ALLOW:
            return ("continue", value, event)

        return self._dispatch_non_allow_decision(
            rail=rail,
            phase=phase,
            event=event,
            value=value,
            decision=decision,
            traces=traces,
            apply_transform=apply_transform,
        )

    def _run_chain(
        self,
        *,
        rails: Iterable[LLMGuardrail],
        phase: LLMGuardrailPhase,
        event: LLMGuardrailEvent,
        value: _TValue,
        apply_transform: Callable[[_TValue, GuardrailDecision], _TValue],
    ) -> tuple[_TValue, list[GuardrailTrace], GuardrailDecision | None]:
        traces: list[GuardrailTrace] = []

        for rail in rails:
            step = self._eval_one_rail(
                rail=rail,
                phase=phase,
                event=event,
                value=value,
                traces=traces,
                apply_transform=apply_transform,
            )
            if step[0] == "stop":
                return step[1], traces, step[2]
            _, value, event = step

        return value, traces, None

    def run_llm_input(
        self, event: LLMGuardrailEvent
    ) -> tuple[MessageHistory, list[GuardrailTrace], GuardrailDecision | None]:
        input_event = (
            event
            if event.phase == LLMGuardrailPhase.INPUT
            else event.model_copy(update={"phase": LLMGuardrailPhase.INPUT})
        )
        input_event = input_event.model_copy(update={"output_message": None})

        def apply_transform(
            current: MessageHistory, decision: GuardrailDecision
        ) -> MessageHistory:
            # NOTE: `current` is intentionally unused here. We keep a uniform
            # (current_value, decision) -> new_value adapter signature for both
            # input/output so `_run_chain` can stay generic. If we later want
            # incremental/patch transforms, we can start using `current` (or
            # change the signature).
            if decision.messages is None:
                raise ValueError(
                    "Input guardrail returned TRANSFORM without decision.messages."
                )
            return decision.messages

        value, traces, blocked = self._run_chain(
            rails=cast(Iterable[LLMGuardrail], self.guard.input),
            phase=LLMGuardrailPhase.INPUT,
            event=input_event,
            value=input_event.messages,
            apply_transform=apply_transform,
        )
        return value, traces, blocked

    def run_llm_output(
        self, event: LLMGuardrailEvent, output: Message
    ) -> tuple[Message, list[GuardrailTrace], GuardrailDecision | None]:
        output_event = (
            event
            if event.phase == LLMGuardrailPhase.OUTPUT
            else event.model_copy(update={"phase": LLMGuardrailPhase.OUTPUT})
        )
        output_event = output_event.model_copy(update={"output_message": output})

        def apply_transform(current: Message, decision: GuardrailDecision) -> Message:
            # Same rationale as input: signature stays uniform across phases.
            if decision.output_message is None:
                raise ValueError(
                    "Output guardrail returned TRANSFORM without decision.output_message."
                )
            return decision.output_message

        value, traces, blocked = self._run_chain(
            rails=cast(Iterable[LLMGuardrail], self.guard.output),
            phase=LLMGuardrailPhase.OUTPUT,
            event=output_event,
            value=output,
            apply_transform=apply_transform,
        )
        return value, traces, blocked
