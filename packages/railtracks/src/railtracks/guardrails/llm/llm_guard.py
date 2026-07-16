from pydantic import BaseModel
from railtracks.context.central import get_parent_id, get_run_id, is_context_present
from railtracks.guardrails.core.decision import GuardrailAction, GuardrailDecision
from railtracks.guardrails.core.errors import GuardrailBlockedError
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.guardrails.core.trace import GuardrailTrace
from railtracks.guardrails.llm.concrete import logger
from railtracks.guardrails.core.interfaces import BaseGuardrail
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message, UserMessage
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool


from abc import abstractmethod
from typing import Any, Generic, TypeVar, cast
from typing_extensions import Literal

_TValue = TypeVar("_TValue", bound=MessageHistory | Message)


class BaseLLMGuardrail(BaseGuardrail[[MessageHistory, type[BaseModel] | None, list[Tool] | None], Response], Generic[_TValue]):
    """Abstract base class for guardrails that run on LLM input or output.

    Attributes:
        phase: Whether this rail expects :class:`LLMGuardrailPhase` ``INPUT`` or
            ``OUTPUT`` events.
    """

    phase: LLMGuardrailPhase

    def __init__(self, name: str | None = None, fail_open: bool = False):
        """Initialize the guardrail.

        Args:
            name: Rail name for traces and debugging; defaults to the class name.
            fail_open: Whether to allow the request to continue when this guard raises an unexpected exception.
        """
        super().__init__(name=name)
        self.fail_open = fail_open


    @abstractmethod
    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        """Evaluate the event and return a decision. Implemented by each concrete guard."""
        pass

    @abstractmethod
    def convert(self, value: str | Any | MessageHistory | LLMGuardrailEvent, /) -> LLMGuardrailEvent:
        """Build an event from a raw value. Implemented per phase by InputGuard and OutputGuard."""
        pass

    def decide(self, value: str | Any | MessageHistory | LLMGuardrailEvent, /) -> GuardrailDecision:
        """Convert value to an event and run this guard on it directly, outside a chain."""
        converted_event = self.convert(value)

        return self(converted_event)

    @staticmethod
    def _coerce_to_message_history(
        input: str | Any | MessageHistory,
    ) -> MessageHistory:
        """Convert str, Message, or MessageHistory to a MessageHistory."""
        if isinstance(input, MessageHistory):
            return input
        if isinstance(input, str):
            return MessageHistory([UserMessage(input)])
        if isinstance(input, Message):
            return MessageHistory([input])
        raise TypeError(
            f"Expected str, Message, MessageHistory, or LLMGuardrailEvent, "
            f"got {type(input).__name__}"
        )


    @staticmethod
    def _node_metadata() -> tuple[str | None, str | None]:
        """``(node_uuid, run_id)`` for event observability.

        Returns ``(None, None)`` when no run context is active — the gate logic never
        depends on this metadata, so it must not raise just to populate it.
        """
        if not is_context_present():
            return None, None
        return get_parent_id(), get_run_id()

    @staticmethod
    def _record_guard_traces(traces: list[GuardrailTrace]) -> None:
        """The single sink for guardrail traces.

        TODO: Determine the correct home for observability traces. For now, just log them at debug level.
        """
        for t in traces:
            logger.debug("guardrail trace: %s", t)

    @staticmethod
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

    def _handle_rail_exception(
        self,
        *,
        exc: Exception,
        traces: list[GuardrailTrace],
        value: _TValue,
        reason_prefix: str,
    ) -> (
        tuple[Literal["continue"], _TValue] | tuple[Literal["stop"], _TValue, GuardrailDecision]
    ):
        """Record exc as a trace and return a stop outcome with a blocking decision."""
        traces.append(self._trace_for_exception(exc=exc))

        if self.fail_open:
            return ("continue", value)
        
        block = GuardrailDecision.block(
            reason=f"{reason_prefix}: {self._rail_name()}",
            user_facing_message="Request blocked by guardrails.",
            meta={
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc),
            },
        )
        return ("stop", value, block)

    def run(
        self,
        *,
        event: LLMGuardrailEvent,
        value: _TValue,
    ) -> tuple[_TValue, list[GuardrailTrace], GuardrailDecision | None]:
        """Run this guard once on event and value.

        Returns the resulting value, the traces recorded, and a blocking decision
        if the run stopped, or None if it completed.
        """
        traces: list[GuardrailTrace] = []


        step = self._eval_one_rail(
                event=event,
                value=value,
                traces=traces,
        )
        if step[0] == "stop":
                return step[1], traces, step[2]

        _, value, event = step

        return value, traces, None


    def _eval_one_rail(
        self,
        event: LLMGuardrailEvent,
        value: _TValue,
        traces: list[GuardrailTrace],
    ) -> (
        tuple[Literal["continue"], _TValue, LLMGuardrailEvent]
        | tuple[Literal["stop"], _TValue, GuardrailDecision]
    ):
        """Call this guard, validate the returned decision, and dispatch it."""
        try:
            decision = self(event)
            if not isinstance(decision, GuardrailDecision):
                raise TypeError(
                    f"Guardrail {self._rail_name()} returned {type(decision).__name__}, expected GuardrailDecision."
                )
        except Exception as e:
            outcome = self._handle_rail_exception(
                exc=e,
                traces=traces,
                value=value,
                reason_prefix="Guardrail raised exception",
            )
            if outcome[0] == "continue":
                return ("continue", value, event)
            return ("stop", outcome[1], outcome[2])

        traces.append(self._trace_from_decision(decision=decision))

        if decision.action == GuardrailAction.ALLOW:
            return ("continue", value, event)

        return self._dispatch_non_allow_decision(
            event=event,
            value=value,
            decision=decision,
            traces=traces,
        )



    def _dispatch_non_allow_decision(
        self,
        *,
        event: LLMGuardrailEvent,
        value: _TValue,
        decision: GuardrailDecision,
        traces: list[GuardrailTrace],
    ) -> (
        tuple[Literal["continue"], _TValue, LLMGuardrailEvent]
        | tuple[Literal["stop"], _TValue, GuardrailDecision]
    ):
        """Apply a TRANSFORM, BLOCK, or unknown-action decision returned by this guard."""
        if decision.action == GuardrailAction.TRANSFORM:
            try:
                value = self._extract_transform_value(decision)
                event = self._sync_event_after_transform(event, value)
            except Exception as e:
                outcome = self._handle_rail_exception(
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
                rail_name=self._rail_name(),
                phase=self.phase.value,
                action="error",
                reason="Unknown guardrail action",
                meta={"action": str(decision.action)},
            )
        )

        if self.fail_open:
            return ("continue", value, event)

        block = GuardrailDecision.block(
            reason=f"Unknown guardrail action from {self._rail_name()}",
            user_facing_message="Request blocked by guardrails.",
        )
        return ("stop", value, block)

    @abstractmethod
    def _sync_event_after_transform(
        self,
        event: LLMGuardrailEvent,
        value: _TValue,
    ) -> LLMGuardrailEvent:
        """Return a copy of event updated with the transformed value. Implemented per phase."""
        pass

    @abstractmethod
    def _extract_transform_value(
        self,
        decision: GuardrailDecision
    ) -> _TValue:
       """Extract the replacement value from a TRANSFORM decision. Implemented per phase."""
       pass

    def _rail_name(self) -> str:
        """Return this guard's name, falling back to its class name if unset."""
        name = self.name
        if isinstance(name, str) and name.strip():
            return name

        return self.__class__.__name__

    def _trace_from_decision(
        self,

        decision: GuardrailDecision,
    ) -> GuardrailTrace:
        """Build a trace recording this guard's decision."""
        return GuardrailTrace(
            rail_name=self._rail_name(),
            phase=self.phase.value,
            action=decision.action.value,
            reason=decision.reason,
            meta=decision.meta,
        )


    def _trace_for_exception(
        self,
        *,
        exc: Exception,
    ) -> GuardrailTrace:
        """Build a trace recording an exception raised by this guard."""
        return GuardrailTrace(
            rail_name=self._rail_name(),
            phase=self.phase.value,
            action="error",
            reason="Guardrail raised exception",
            meta={
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc),
            },
        )