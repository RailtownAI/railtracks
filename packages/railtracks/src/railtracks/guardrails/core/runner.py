from __future__ import annotations

from typing import Callable, Iterable, TypeVar, cast

from railtracks.llm.message import Message
from railtracks.llm.history import MessageHistory

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
            try:
                decision = rail(event)
                if not isinstance(decision, GuardrailDecision):
                    raise TypeError(
                        f"Guardrail {_rail_name(rail)!r} returned {type(decision).__name__}, expected GuardrailDecision."
                    )
            except Exception as e:
                traces.append(_trace_for_exception(rail=rail, phase=phase, exc=e))
                if self.guard.fail_open:
                    continue
                block = GuardrailDecision.block(
                    reason=f"Guardrail raised exception: {_rail_name(rail)}",
                    user_facing_message="Request blocked by guardrails.",
                    meta={
                        "exception_type": e.__class__.__name__,
                        "exception_message": str(e),
                    },
                )
                return value, traces, block

            traces.append(
                _trace_from_decision(rail=rail, phase=phase, decision=decision)
            )

            if decision.action == GuardrailAction.ALLOW:
                continue

            if decision.action == GuardrailAction.TRANSFORM:
                try:
                    value = apply_transform(value, decision)
                    # Propagate intermediate transforms so subsequent rails see updates.
                    if phase == LLMGuardrailPhase.INPUT:
                        event = event.model_copy(
                            update={"messages": cast(MessageHistory, value)}
                        )
                    elif phase == LLMGuardrailPhase.OUTPUT:
                        event = event.model_copy(
                            update={"output_message": cast(Message, value)}
                        )
                except Exception as e:
                    traces.append(
                        _trace_for_exception(rail=rail, phase=phase, exc=e)
                    )
                    if self.guard.fail_open:
                        continue
                    block = GuardrailDecision.block(
                        reason=f"Guardrail transform failed: {_rail_name(rail)}",
                        user_facing_message="Request blocked by guardrails.",
                        meta={
                            "exception_type": e.__class__.__name__,
                            "exception_message": str(e),
                        },
                    )
                    return value, traces, block
                continue

            if decision.action == GuardrailAction.BLOCK:
                return value, traces, decision

            # Defensive: future-proof unknown actions
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
                continue
            block = GuardrailDecision.block(
                reason=f"Unknown guardrail action from {_rail_name(rail)}",
                user_facing_message="Request blocked by guardrails.",
            )
            return value, traces, block

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

