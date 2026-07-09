"""Unit tests for the guardrail middleware gates (guardrail_gates.py).

These replace the LLMGuardrailsMixin seam: input guards -> entry gate, output guards ->
exit gate, both delegating to GuardRunner. Tests exercise the gates directly via
apply_entry / apply_exit, and end-to-end through a MiddlewareChain wired the way
ModelInvoker wires them (input as sys entry position="after", output as sys exit).
"""

from __future__ import annotations

import pytest

from railtracks.guardrails.core import (
    Guard,
    GuardrailBlockedError,
    GuardrailDecision,
    InputGuard,
    LLMGuardrailEvent,
    OutputGuard,
)
from railtracks.guardrails.llm.guardrail_gates import (
    guardrail_input_middleware,
    guardrail_output_middleware,
)
from railtracks.llm import AssistantMessage, MessageHistory, UserMessage
from railtracks.llm.content import ToolCall
from railtracks.llm.response import MessageInfo, Response
from railtracks.middlewares import MiddlewareChain


# --------------------------------------------------------------------------- helpers


class FnInputGuard(InputGuard):
    def __init__(self, fn, name: str | None = None):
        super().__init__(name=name)
        self._fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._fn(event)


class FnOutputGuard(OutputGuard):
    def __init__(self, fn, name: str | None = None):
        super().__init__(name=name)
        self._fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._fn(event)


def _content_response(text: str = "hi") -> Response:
    return Response(message=AssistantMessage(text), message_info=MessageInfo(model_name="m"))


def _tool_call_response() -> Response:
    msg = AssistantMessage(content=[ToolCall(identifier="1", name="foo", arguments={})])
    return Response(message=msg, message_info=MessageInfo(model_name="m"))


# --------------------------------------------------------------------------- input gate


class TestInputGate:
    @pytest.mark.asyncio
    async def test_empty_input_rails_passes_through(self):
        gate = guardrail_input_middleware(Guard(input=[]))
        args, kwargs = await gate.apply_entry(MessageHistory([UserMessage("x")]), None, None)
        assert kwargs == {}
        assert isinstance(args[0], MessageHistory)

    @pytest.mark.asyncio
    async def test_allow_passes_through_unchanged(self):
        gate = guardrail_input_middleware(
            Guard(input=[FnInputGuard(lambda _e: GuardrailDecision.allow(reason="ok"))])
        )
        mh = MessageHistory([UserMessage("x")])
        args, kwargs = await gate.apply_entry(mh, None, None)
        assert args[0] is mh  # unchanged object flows through

    @pytest.mark.asyncio
    async def test_block_raises(self):
        gate = guardrail_input_middleware(
            Guard(
                input=[
                    FnInputGuard(
                        lambda _e: GuardrailDecision.block(reason="nope", user_facing_message="u"),
                        name="blocker",
                    )
                ]
            )
        )
        with pytest.raises(GuardrailBlockedError) as exc:
            await gate.apply_entry(MessageHistory([UserMessage("x")]), None, None)
        assert exc.value.reason == "nope"
        assert exc.value.user_facing_message == "u"
        assert exc.value.rail_name == "blocker"
        assert exc.value.traces and exc.value.traces[-1].action == "block"

    @pytest.mark.asyncio
    async def test_transform_forwards_new_messages_and_keeps_schema_tools(self):
        new_hist = MessageHistory([UserMessage("redacted")])
        gate = guardrail_input_middleware(
            Guard(
                input=[
                    FnInputGuard(
                        lambda _e: GuardrailDecision.transform_messages(
                            messages=new_hist, reason="edit"
                        )
                    )
                ]
            )
        )
        schema, tools = object(), ["t"]
        args, kwargs = await gate.apply_entry(MessageHistory([UserMessage("x")]), schema, tools)
        # full (messages, schema, tools) replacement — schema/tools preserved
        assert args == (new_hist, schema, tools)
        assert kwargs == {}


# --------------------------------------------------------------------------- output gate


class TestOutputGate:
    @pytest.mark.asyncio
    async def test_empty_output_rails_passes_through(self):
        gate = guardrail_output_middleware(Guard(output=[]))
        resp = _content_response()
        assert await gate.apply_exit(resp) is resp

    @pytest.mark.asyncio
    async def test_intermediate_tool_call_passes_through_untouched(self):
        # A blocking output guard must NOT fire on an intermediate tool-call turn.
        gate = guardrail_output_middleware(
            Guard(output=[FnOutputGuard(lambda _e: GuardrailDecision.block(reason="should not run"))])
        )
        resp = _tool_call_response()
        assert await gate.apply_exit(resp) is resp  # unchanged, no raise

    @pytest.mark.asyncio
    async def test_terminal_block_raises(self):
        gate = guardrail_output_middleware(
            Guard(output=[FnOutputGuard(lambda _e: GuardrailDecision.block(reason="bad output"))])
        )
        with pytest.raises(GuardrailBlockedError) as exc:
            await gate.apply_exit(_content_response("evil"))
        assert exc.value.traces[-1].phase == "llm_output"

    @pytest.mark.asyncio
    async def test_terminal_transform_preserves_message_info(self):
        new_msg = AssistantMessage("sanitized")
        gate = guardrail_output_middleware(
            Guard(
                output=[
                    FnOutputGuard(
                        lambda _e: GuardrailDecision.transform_output(
                            output_message=new_msg, reason="fix"
                        )
                    )
                ]
            )
        )
        info = MessageInfo(input_tokens=3, output_tokens=5, model_name="m")
        resp = Response(message=AssistantMessage("raw"), message_info=info)
        out = await gate.apply_exit(resp)
        assert isinstance(out, Response)
        assert out.message is new_msg
        assert out.message_info is info

    @pytest.mark.asyncio
    async def test_terminal_allow_passes_through(self):
        gate = guardrail_output_middleware(
            Guard(output=[FnOutputGuard(lambda _e: GuardrailDecision.allow(reason="ok"))])
        )
        resp = _content_response()
        assert await gate.apply_exit(resp) is resp


# --------------------------------------------------------------------------- wired like ModelInvoker


def _pii_input_guard():
    from railtracks.guardrails.llm import PIIRedactInputGuard

    return PIIRedactInputGuard()


class TestWiredIntoMiddlewareChain:
    """Wire the gates the way NodeBuilder.llm wires them onto ModelInvoker and run."""

    def _chain(self, guard: Guard) -> MiddlewareChain:
        mc = MiddlewareChain()
        if guard.input:
            mc.register_sys_gate(guardrail_input_middleware(guard), position="after")
        if guard.output:
            mc.register_sys_exit_gate(guardrail_output_middleware(guard))
        return mc

    @pytest.mark.asyncio
    async def test_input_redaction_reaches_core(self):
        seen = {}

        async def core(messages, schema, tools):
            seen["messages"] = messages
            return _content_response("done")

        mc = self._chain(Guard(input=[_pii_input_guard()]))
        original = MessageHistory([UserMessage("email me at alice@example.com")])
        await mc.run(core, original, None, None)

        # The core saw redacted content; the caller's original is untouched.
        assert "[EMAIL_ADDRESS]" in seen["messages"][0].content
        assert "alice@example.com" in original[0].content

    @pytest.mark.asyncio
    async def test_input_gate_runs_every_round_no_latch(self):
        # No latch: redaction is re-applied on every model call, so a second round
        # (same original history) still reaches the core redacted.
        calls = []

        async def core(messages, schema, tools):
            calls.append(messages[0].content)
            return _content_response()

        mc = self._chain(Guard(input=[_pii_input_guard()]))
        original = MessageHistory([UserMessage("ssn 123-45-6789")])
        await mc.run(core, original, None, None)
        await mc.run(core, original, None, None)

        assert len(calls) == 2
        assert all("[US_SSN]" in c for c in calls)  # redacted every round

    @pytest.mark.asyncio
    async def test_output_block_propagates_through_run(self):
        async def core(messages, schema, tools):
            return _content_response("leak")

        mc = self._chain(
            Guard(output=[FnOutputGuard(lambda _e: GuardrailDecision.block(reason="blocked"))])
        )
        with pytest.raises(GuardrailBlockedError):
            await mc.run(core, MessageHistory([UserMessage("q")]), None, None)