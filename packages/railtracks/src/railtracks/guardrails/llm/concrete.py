from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Generic, ParamSpec, Protocol, TypeVar, cast, cast, overload
from typing_extensions import Literal

from pydantic import BaseModel
from railtracks.context.central import get_parent_id, get_run_id, is_context_present

from railtracks.guardrails.core.trace import GuardrailTrace
from railtracks.guardrails.llm.interfaces import BaseGuardrail
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage, Message, UserMessage
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middleware.core import Middleware

from ..core.decision import GuardrailDecision
from ..core.event import LLMGuardrailEvent, LLMGuardrailPhase

from typing import Awaitable, Callable

from pydantic import BaseModel
from railtracks.context.central import get_parent_id, get_run_id, is_context_present
from railtracks.guardrails.core.decision import GuardrailAction, GuardrailDecision
from railtracks.guardrails.core.errors import GuardrailBlockedError
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.guardrails.core.trace import GuardrailTrace
from railtracks.llm.history import MessageHistory
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.utils.logging.create import get_rt_logger

from railtracks.built_nodes.llm.middleware.core import ModelMiddleware

logger = get_rt_logger("guardrails")

_TValue = TypeVar("_TValue", bound=MessageHistory | Message)



class BaseLLMGuardrail(BaseGuardrail[[MessageHistory, type[BaseModel] | None, list[Tool] | None], Response], Generic[_TValue]):
    """Abstract base class for guardrails that run on LLM input or output.

    Attributes:
        phase: Whether this rail expects :class:`LLMGuardrailPhase` ``INPUT`` or
            ``OUTPUT`` events.
    """

    phase: LLMGuardrailPhase

    @abstractmethod
    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        pass
    
    @abstractmethod
    def convert(self, value: str | Any | MessageHistory | LLMGuardrailEvent, /) -> LLMGuardrailEvent:
        pass

    def decide(self, value: str | Any | MessageHistory | LLMGuardrailEvent, /) -> GuardrailDecision:
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
        traces.append(self._trace_for_exception(exc=exc))
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
        if self.phase == LLMGuardrailPhase.INPUT:
            return event.model_copy(update={"messages": cast(MessageHistory, value)})
        return event.model_copy(update={"output_message": cast(Message, value)})

    @abstractmethod
    def _extract_transform_value(
        self,
        decision: GuardrailDecision
    ) -> _TValue:
       pass

    def _rail_name(self) -> str:
        name = self.name
        if isinstance(name, str) and name.strip():
            return name
        
        return self.__class__.__name__

    def _trace_from_decision(
        self,

        decision: GuardrailDecision,
    ) -> GuardrailTrace:
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


class InputGuard(BaseLLMGuardrail[MessageHistory]):
    """Base for guardrails that run on LLM input (e.g. prompt / message history).

    Attributes:
        phase: Always :attr:`LLMGuardrailPhase.INPUT`.
    """

    phase = LLMGuardrailPhase.INPUT


    async def _middleware_fn(
        self,
        call: Callable[
                [MessageHistory, type[BaseModel] | None, list[Tool] | None],
                Awaitable[Response],
            ],
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ):
        message_history, schema, tools = self._input_wrapper(
            message_history, schema, tools
        )
        return await call(message_history, schema, tools)


    def _input_wrapper(
        self,
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ):
        node_uuid, run_id = self._node_metadata()
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.INPUT,
            messages=message_history,
            node_uuid=node_uuid,
            run_id=run_id,
        )
        
        new_messages, traces, decision = self.run(event=event, value=message_history)
        self._record_guard_traces(traces)
        self._raise_if_blocked(decision, traces)

        return new_messages, schema, tools

        

    def convert(
        self,
        value: str | Any | MessageHistory | LLMGuardrailEvent,
        /,
    ):
        """Run this guard without building an :class:`LLMGuardrailEvent` by hand.

        Args:
            value: A :class:`LLMGuardrailEvent` (passed through), a ``str`` (treated
                as a single user message), a :class:`~railtracks.llm.message.Message`,
                or a :class:`~railtracks.llm.history.MessageHistory`.

        Returns:
            The :class:`GuardrailDecision` from :meth:`__call__`.

        Raises:
            TypeError: If ``value`` is not a ``str``, ``Message``, ``MessageHistory``,
                or :class:`LLMGuardrailEvent`.
        """
        if isinstance(value, LLMGuardrailEvent):
            return value

        messages = self._coerce_to_message_history(value)
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.INPUT,
            messages=messages,
        )
        return event

    def _extract_transform_value(self, decision: GuardrailDecision) -> Any:
        
            if decision.messages is None:
                raise ValueError(
                    "Input guardrail returned TRANSFORM without decision.messages."
                )
            return decision.messages
    
    def _sync_event_after_transform(
        self,
        event: LLMGuardrailEvent,
        value: MessageHistory,
    ) -> LLMGuardrailEvent:
        
        return event.model_copy(update={"messages": cast(MessageHistory, value)})
        
        


class OutputGuard(BaseLLMGuardrail[Message]):
    """Base for guardrails that run on LLM output (e.g. model response).

    Inspect ``event.output_message`` for the assistant message produced this turn.
    ``event.messages`` is conversation context and may not yet include that reply.

    Attributes:
        phase: Always :attr:`LLMGuardrailPhase.OUTPUT`.
    """

    phase = LLMGuardrailPhase.OUTPUT

    async def _middleware_fn(
        self,
        call: Callable[
                [MessageHistory, type[BaseModel] | None, list[Tool] | None],
                Awaitable[Response],
            ],
        message_history: MessageHistory,
        schema: type[BaseModel] | None,
        tools: list[Tool] | None,
    ):
        result = await call(message_history, schema, tools)
        return self._output_wrapper(result=result)

        


    def _output_wrapper(
        self,
        result: Response,
    ):
        
        node_uuid, run_id = self._node_metadata()
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([]), 
            output_message=result.message,
            node_uuid=node_uuid,
            run_id=run_id,
        )
        new_message, traces, decision = self.run(event=event, value=result.message)
        self._record_guard_traces(traces)
        self._raise_if_blocked(decision, traces)

        if new_message is result.message:
            return result
        
        return Response(message=new_message, message_info=result.message_info)

    def convert(
        self,
        output: str | Any | MessageHistory | LLMGuardrailEvent,
        /
    ):
        """Run this guard without building an :class:`LLMGuardrailEvent` by hand.

        Args:
            output: A :class:`LLMGuardrailEvent` (passed through), a ``str`` (becomes
                the assistant message with empty prior history), a
                :class:`~railtracks.llm.message.Message`, or a non-empty
                :class:`~railtracks.llm.history.MessageHistory` (last message is the
                output under test; earlier entries become ``event.messages``).

        Returns:
            The :class:`GuardrailDecision` from :meth:`__call__`.

        Raises:
            ValueError: If ``output`` is an empty :class:`~railtracks.llm.history.MessageHistory`.
            TypeError: If ``output`` is not a ``str``, ``Message``, ``MessageHistory``,
                or :class:`LLMGuardrailEvent`.
        """
        if isinstance(output, LLMGuardrailEvent):
            return output

        if isinstance(output, str):
            output_message = AssistantMessage(output)
            messages = MessageHistory()
        elif isinstance(output, Message):
            output_message = output
            messages = MessageHistory()
        elif isinstance(output, MessageHistory):
            if not output:
                raise ValueError("Cannot decide with an empty MessageHistory.")
            output_message = output[-1]
            messages = MessageHistory(output[:-1])
        else:
            raise TypeError(
                f"Expected str, Message, MessageHistory, or LLMGuardrailEvent, "
                f"got {type(output).__name__}"
            )

        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=messages,
            output_message=output_message,
        )
        return event
    
    def _extract_transform_value(self, decision: GuardrailDecision) -> Message:
        if decision.output_message is None:
            raise ValueError(
                "Output guardrail returned TRANSFORM without decision.output_message."
            )
        return decision.output_message

    def _sync_event_after_transform(
        self,
        event: LLMGuardrailEvent,
        value: Message,
    ) -> LLMGuardrailEvent:
        return event.model_copy(update={"output_message": cast(Message, value)})
