from __future__ import annotations

from typing import (
    Any,
    Awaitable,
    Callable,
    cast,
)

from pydantic import BaseModel

from railtracks.guardrails.llm.llm_guard import BaseLLMGuardrail
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage, Message
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.utils.logging.create import get_rt_logger

from ..core.decision import GuardrailDecision
from ..core.event import LLMGuardrailEvent, LLMGuardrailPhase

logger = get_rt_logger("guardrails")


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
        """Run this guard on the message history, then call onward with the result."""
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
        """Build the input event, run this guard, and raise if it blocks."""
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
        """Return the replacement messages from a TRANSFORM decision."""
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
        """Return a copy of event with its messages replaced."""
        return event.model_copy(update={"messages": value})


def _is_intermediate_tool_call(response: Response) -> bool:
    """A model round-trip is *intermediate* (not the final reply) when it requests tools.

    Mirrors ``process_message`` in ``llm_helpers`` (tool calls present => "Tool").
    """
    return len(response.message.tool_calls) > 0


class OutputGuard(BaseLLMGuardrail[Message]):
    """Base for guardrails that run on LLM output (e.g. model response).

    Inspect ``event.output_message`` for the assistant message produced this turn.
    ``event.messages`` is conversation context and may not yet include that reply.

    Intermediate tool-call turns pass through untouched, so output rails fire only
    on the final reply.

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
        """Call onward for the response, then run this guard on the final reply.

        Responses that request tools are intermediate steps of the tool-calling
        loop and pass through unguarded.
        """
        result = await call(message_history, schema, tools)
        if _is_intermediate_tool_call(result):
            return result
        return self._output_wrapper(result=result)

    def _output_wrapper(
        self,
        result: Response,
    ):
        """Build the output event, run this guard, and rebuild the response if the message changed."""
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

    def convert(self, output: str | Any | MessageHistory | LLMGuardrailEvent, /):
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
        """Return the replacement output message from a TRANSFORM decision."""
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
        """Return a copy of event with its output message replaced."""
        return event.model_copy(update={"output_message": cast(Message, value)})
