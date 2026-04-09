from __future__ import annotations

from typing import Any, Iterable, Literal, cast

from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message

from .config import Guard
from .decision import GuardrailAction, GuardrailDecision
from .event import LLMGuardrailEvent, LLMGuardrailPhase
from .interfaces import BaseLLMGuardrail
from .trace import GuardrailTrace


def _rail_name(rail: BaseLLMGuardrail) -> str:
    name = getattr(rail, "name", None)
    if isinstance(name, str) and name.strip():
        return name
    return rail.__class__.__name__


def _trace_from_decision(
    *,
    rail: BaseLLMGuardrail,
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
    rail: BaseLLMGuardrail,
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


def _extract_transform_value(
    phase: LLMGuardrailPhase, decision: GuardrailDecision
) -> Any:
    if phase == LLMGuardrailPhase.INPUT:
        if decision.messages is None:
            raise ValueError(
                "Input guardrail returned TRANSFORM without decision.messages."
            )
        return decision.messages
    if decision.output_message is None:
        raise ValueError(
            "Output guardrail returned TRANSFORM without decision.output_message."
        )
    return decision.output_message


class GuardRunner:
    """Runs LLM input and output guardrail chains for a :class:`Guard` configuration.

    For each rail, records a :class:`GuardrailTrace`. If a rail raises, returns invalid
    output types, or uses an unknown action, behavior depends on ``guard.fail_open``:
    when True, processing continues with the last good value; when False, the chain
    stops and the third return value is a blocking :class:`GuardrailDecision`.
    """

    def __init__(self, guard: Guard):
        self.guard = guard

    def _sync_event_after_transform(
        self,
        phase: LLMGuardrailPhase,
        event: LLMGuardrailEvent,
        value: Any,
    ) -> LLMGuardrailEvent:
        if phase == LLMGuardrailPhase.INPUT:
            return event.model_copy(update={"messages": cast(MessageHistory, value)})
        return event.model_copy(update={"output_message": cast(Message, value)})

    def _handle_rail_exception(
        self,
        *,
        rail: BaseLLMGuardrail,
        phase: LLMGuardrailPhase,
        exc: Exception,
        traces: list[GuardrailTrace],
        value: Any,
        reason_prefix: str,
    ) -> (
        tuple[Literal["continue"], Any] | tuple[Literal["stop"], Any, GuardrailDecision]
    ):
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
        rail: BaseLLMGuardrail,
        phase: LLMGuardrailPhase,
        event: LLMGuardrailEvent,
        value: Any,
        decision: GuardrailDecision,
        traces: list[GuardrailTrace],
    ) -> (
        tuple[Literal["continue"], Any, LLMGuardrailEvent]
        | tuple[Literal["stop"], Any, GuardrailDecision]
    ):
        if decision.action == GuardrailAction.TRANSFORM:
            try:
                value = _extract_transform_value(phase, decision)
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
        rail: BaseLLMGuardrail,
        phase: LLMGuardrailPhase,
        event: LLMGuardrailEvent,
        value: Any,
        traces: list[GuardrailTrace],
    ) -> (
        tuple[Literal["continue"], Any, LLMGuardrailEvent]
        | tuple[Literal["stop"], Any, GuardrailDecision]
    ):
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

        traces.append(_trace_from_decision(rail=rail, phase=phase, decision=decision))

        if decision.action == GuardrailAction.ALLOW:
            return ("continue", value, event)

        return self._dispatch_non_allow_decision(
            rail=rail,
            phase=phase,
            event=event,
            value=value,
            decision=decision,
            traces=traces,
        )

    def _run_chain(
        self,
        *,
        rails: Iterable[BaseLLMGuardrail],
        phase: LLMGuardrailPhase,
        event: LLMGuardrailEvent,
        value: Any,
    ) -> tuple[Any, list[GuardrailTrace], GuardrailDecision | None]:
        traces: list[GuardrailTrace] = []

        for rail in rails:
            step = self._eval_one_rail(
                rail=rail,
                phase=phase,
                event=event,
                value=value,
                traces=traces,
            )
            if step[0] == "stop":
                return step[1], traces, step[2]
            _, value, event = step

        return value, traces, None

    def run_llm_input(
        self, event: LLMGuardrailEvent
    ) -> tuple[MessageHistory, list[GuardrailTrace], GuardrailDecision | None]:
        """Run all input rails on ``event.messages``.

        Normalizes ``event`` to input phase and clears ``output_message`` so input
        guards see a consistent :class:`LLMGuardrailEvent`.

        Args:
            event: Any LLM guardrail event; phase may be coerced to ``INPUT`` and
                ``output_message`` cleared before running the chain.

        Returns:
            A tuple ``(messages, traces, decision)``. ``messages`` is the possibly
            transformed :class:`~railtracks.llm.history.MessageHistory`. ``traces``
            lists each rail outcome, including ``action="error"`` when a rail raised
            or returned an invalid result (if ``fail_open`` allowed continuation).
            ``decision`` is ``None`` when the chain completed without a stop.
            Otherwise it is a :class:`GuardrailDecision` with action ``block`` produced
            when ``fail_open`` is False (rail exception, bad transform, unknown action).
        """
        input_event = (
            event
            if event.phase == LLMGuardrailPhase.INPUT
            else event.model_copy(update={"phase": LLMGuardrailPhase.INPUT})
        )
        input_event = input_event.model_copy(update={"output_message": None})

        value, traces, blocked = self._run_chain(
            rails=cast(Iterable[BaseLLMGuardrail], self.guard.input),
            phase=LLMGuardrailPhase.INPUT,
            event=input_event,
            value=input_event.messages,
        )
        return value, traces, blocked

    def run_llm_output(
        self, event: LLMGuardrailEvent, output: Message
    ) -> tuple[Message, list[GuardrailTrace], GuardrailDecision | None]:
        """Run all output rails on ``output`` with ``event`` as context.

        Ensures ``event.phase`` is ``OUTPUT`` and sets ``event.output_message`` to
        ``output`` before running the chain.

        Args:
            event: Conversation context for the guardrail call; phase may be coerced to
                ``OUTPUT``.
            output: The assistant :class:`~railtracks.llm.message.Message` to guard.

        Returns:
            A tuple ``(message, traces, decision)``. ``message`` is the possibly
            transformed assistant message. ``traces`` lists each rail outcome, including
            ``action="error"`` when a rail raised or returned an invalid result (if
            ``fail_open`` allowed continuation). ``decision`` is ``None`` when the
            chain completed without a stop. Otherwise it is a blocking
            :class:`GuardrailDecision` when ``fail_open`` is False (rail exception,
            bad transform, unknown action).
        """
        output_event = (
            event
            if event.phase == LLMGuardrailPhase.OUTPUT
            else event.model_copy(update={"phase": LLMGuardrailPhase.OUTPUT})
        )
        output_event = output_event.model_copy()
        output_event.output_message = output

        value, traces, blocked = self._run_chain(
            rails=cast(Iterable[BaseLLMGuardrail], self.guard.output),
            phase=LLMGuardrailPhase.OUTPUT,
            event=output_event,
            value=output,
        )
        return value, traces, blocked
