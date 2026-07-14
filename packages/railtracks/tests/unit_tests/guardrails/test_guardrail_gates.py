"""Unit tests for the guardrail-as-middleware adapters (guardrail_gates.py).

`guardrail_input_middleware` / `guardrail_output_middleware` are thin `@before_model` /
`@after_model` adapters over `GuardRunner`. Since the real `Middleware` primitive has no
separate entry/exit-gate concept, each is exercised by calling `.wrap(core)` directly and
awaiting the result, plus end-to-end through a real `MiddlewareChain` wired the way
`NodeBuilder.llm` wires them onto `ModelInvoker`.
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
from railtracks.middleware import MiddlewareChain

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
    return Response(
        message=AssistantMessage(text), message_info=MessageInfo(model_name="m")
    )


def _tool_call_response() -> Response:
    msg = AssistantMessage(content=[ToolCall(identifier="1", name="foo", arguments={})])
    return Response(message=msg, message_info=MessageInfo(model_name="m"))


# --------------------------------------------------------------------------- input middleware


class TestInputMiddleware:
    async def test_empty_input_rails_passes_through(self):
        mw = guardrail_input_middleware(Guard(input=[]))
        seen = {}

        async def core(messages, schema, tools):
            seen["messages"] = messages
            return _content_response()

        await mw.wrap(core)(MessageHistory([UserMessage("x")]), None, None)
        assert isinstance(seen["messages"], MessageHistory)

    async def test_allow_passes_through_unchanged(self):
        mw = guardrail_input_middleware(
            Guard(input=[FnInputGuard(lambda _e: GuardrailDecision.allow(reason="ok"))])
        )
        mh = MessageHistory([UserMessage("x")])
        seen = {}

        async def core(messages, schema, tools):
            seen["messages"] = messages
            return _content_response()

        await mw.wrap(core)(mh, None, None)
        assert seen["messages"] is mh  # unchanged object flows through

    async def test_block_raises(self):
        mw = guardrail_input_middleware(
            Guard(
                input=[
                    FnInputGuard(
                        lambda _e: GuardrailDecision.block(
                            reason="nope", user_facing_message="u"
                        ),
                        name="blocker",
                    )
                ]
            )
        )

        async def core(messages, schema, tools):
            raise AssertionError("core should not run")

        with pytest.raises(GuardrailBlockedError) as exc:
            await mw.wrap(core)(MessageHistory([UserMessage("x")]), None, None)
        assert exc.value.reason == "nope"
        assert exc.value.user_facing_message == "u"
        assert exc.value.rail_name == "blocker"
        assert exc.value.traces and exc.value.traces[-1].action == "block"

    async def test_transform_forwards_new_messages_and_keeps_schema_tools(self):
        new_hist = MessageHistory([UserMessage("redacted")])
        mw = guardrail_input_middleware(
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
        seen = {}
        schema, tools = object(), ["t"]

        async def core(messages, schema_, tools_):
            seen["args"] = (messages, schema_, tools_)
            return _content_response()

        await mw.wrap(core)(MessageHistory([UserMessage("x")]), schema, tools)
        assert seen["args"] == (new_hist, schema, tools)

    async def test_runs_on_every_call_no_latch(self):
        """No latch: redaction is re-applied on every model round-trip."""
        calls = []
        mw = guardrail_input_middleware(
            Guard(
                input=[
                    FnInputGuard(
                        lambda _e: GuardrailDecision.transform_messages(
                            messages=MessageHistory([UserMessage("redacted")]),
                            reason="x",
                        )
                    )
                ]
            )
        )

        async def core(messages, schema, tools):
            calls.append(messages[0].content)
            return _content_response()

        wrapped = mw.wrap(core)
        await wrapped(MessageHistory([UserMessage("secret")]), None, None)
        await wrapped(MessageHistory([UserMessage("secret")]), None, None)
        assert calls == ["redacted", "redacted"]


# --------------------------------------------------------------------------- output middleware


class TestOutputMiddleware:
    async def test_empty_output_rails_passes_through(self):
        mw = guardrail_output_middleware(Guard(output=[]))
        resp = _content_response()

        async def core(messages, schema, tools):
            return resp

        assert await mw.wrap(core)(MessageHistory(), None, None) is resp

    async def test_intermediate_tool_call_passes_through_untouched(self):
        # A blocking output guard must NOT fire on an intermediate tool-call turn.
        mw = guardrail_output_middleware(
            Guard(
                output=[
                    FnOutputGuard(
                        lambda _e: GuardrailDecision.block(reason="should not run")
                    )
                ]
            )
        )
        resp = _tool_call_response()

        async def core(messages, schema, tools):
            return resp

        assert await mw.wrap(core)(MessageHistory(), None, None) is resp

    async def test_terminal_block_raises(self):
        mw = guardrail_output_middleware(
            Guard(
                output=[FnOutputGuard(lambda _e: GuardrailDecision.block(reason="bad output"))]
            )
        )

        async def core(messages, schema, tools):
            return _content_response("evil")

        with pytest.raises(GuardrailBlockedError) as exc:
            await mw.wrap(core)(MessageHistory(), None, None)
        assert exc.value.traces[-1].phase == "llm_output"

    async def test_terminal_transform_preserves_message_info(self):
        new_msg = AssistantMessage("sanitized")
        mw = guardrail_output_middleware(
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

        async def core(messages, schema, tools):
            return Response(message=AssistantMessage("raw"), message_info=info)

        out = await mw.wrap(core)(MessageHistory(), None, None)
        assert isinstance(out, Response)
        assert out.message is new_msg
        assert out.message_info is info

    async def test_terminal_allow_passes_through(self):
        mw = guardrail_output_middleware(
            Guard(output=[FnOutputGuard(lambda _e: GuardrailDecision.allow(reason="ok"))])
        )
        resp = _content_response()

        async def core(messages, schema, tools):
            return resp

        assert await mw.wrap(core)(MessageHistory(), None, None) is resp


# --------------------------------------------------------------------------- wired like ModelInvoker


def _pii_input_guard():
    from railtracks.guardrails.llm import PIIRedactInputGuard

    return PIIRedactInputGuard()


class TestWiredIntoMiddlewareChain:
    """Wire the gates the way NodeBuilder.llm wires them onto ModelInvoker, then run
    through a real MiddlewareChain (a bare list -- MiddlewareChain has no separate
    entry/exit band, so output is placed before input, matching the actual splice
    order in `_node_builder.py`: `[*user_model_middleware, output_gate, input_gate]`)."""

    def _chain(self, guard: Guard) -> MiddlewareChain:
        middleware = []
        if guard.output:
            middleware.append(guardrail_output_middleware(guard))
        if guard.input:
            middleware.append(guardrail_input_middleware(guard))
        return MiddlewareChain(middleware)

    async def test_input_redaction_reaches_core(self):
        seen = {}

        async def core(messages, schema, tools):
            seen["messages"] = messages
            return _content_response("done")

        chain = self._chain(Guard(input=[_pii_input_guard()]))
        original = MessageHistory([UserMessage("email me at alice@example.com")])
        await chain.run(core, original, None, None)

        # The core saw redacted content; the caller's original is untouched.
        assert "[EMAIL_ADDRESS]" in seen["messages"][0].content
        assert "alice@example.com" in original[0].content

    async def test_input_gate_runs_every_round_no_latch(self):
        # No latch: redaction re-applies on every model call, so a second round (same
        # original history) still reaches the core redacted.
        calls = []

        async def core(messages, schema, tools):
            calls.append(messages[0].content)
            return _content_response()

        chain = self._chain(Guard(input=[_pii_input_guard()]))
        original = MessageHistory([UserMessage("ssn 123-45-6789")])
        await chain.run(core, original, None, None)
        await chain.run(core, original, None, None)

        assert len(calls) == 2
        assert all("[US_SSN]" in c for c in calls)

    async def test_output_block_propagates_through_run(self):
        async def core(messages, schema, tools):
            return _content_response("leak")

        chain = self._chain(
            Guard(output=[FnOutputGuard(lambda _e: GuardrailDecision.block(reason="blocked"))])
        )
        with pytest.raises(GuardrailBlockedError):
            await chain.run(core, MessageHistory([UserMessage("q")]), None, None)
