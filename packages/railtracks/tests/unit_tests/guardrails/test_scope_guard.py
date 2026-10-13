from __future__ import annotations

import asyncio
import json

import pytest
import railtracks as rt
from railtracks.exceptions import LLMError
from railtracks.guardrails.core.decision import GuardrailAction
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.guardrails.llm.concrete import InputGuard
from railtracks.llm import MessageHistory
from railtracks.llm.message import (
    AssistantMessage,
    Role,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from railtracks.prebuilt.guardrails import ScopeGuard, ScopeSensitivity
from railtracks.prebuilt.guardrails.input import scope_guard as scope_module

SCOPE = "You support Acme Cloud billing: invoices, refunds and plan pricing."


def _input_event(messages: MessageHistory) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=messages)


def _judge_llm(mock_llm, label: str, reason: str = "judge reason"):
    """A MockLLM whose structured output is the given label, recording each call."""
    llm = mock_llm(custom_response=json.dumps({"reason": reason, "label": label}))
    seen: dict[str, list] = {"calls": []}
    real = llm._structured

    def wrapped(messages, schema, **kwargs):  # type: ignore[no-untyped-def]
        seen["calls"].append(messages)
        return real(messages, schema, **kwargs)

    llm._structured = wrapped  # type: ignore[method-assign]
    return llm, seen


def _make_guard(mock_llm, label="IN_SCOPE", sensitivity="MEDIUM", scope=SCOPE):
    llm, seen = _judge_llm(mock_llm, label)
    return ScopeGuard(scope, llm, sensitivity=sensitivity), seen


def _judge_user_text(seen: dict[str, list], call: int = 0) -> str:
    return next(m.content for m in seen["calls"][call] if m.role == Role.user)


def _judge_system_text(seen: dict[str, list], call: int = 0) -> str:
    return next(m.content for m in seen["calls"][call] if m.role == Role.system)


class TestConstruction:
    @pytest.mark.parametrize("scope", ["", "   \n\t"])
    def test_blank_scope_raises(self, mock_llm, scope):
        with pytest.raises(ValueError):
            ScopeGuard(scope, mock_llm())

    def test_normal_construction(self, mock_llm):
        guard = ScopeGuard(SCOPE, mock_llm())

        assert isinstance(guard, InputGuard)
        assert guard.fail_open is True
        assert guard._is_async() is True
        assert guard.phase == LLMGuardrailPhase.INPUT

    async def test_model_factory(self, mock_llm):
        llm, _ = _judge_llm(mock_llm, "OUT_OF_SCOPE")
        guard = ScopeGuard(SCOPE, lambda: llm)

        decision = await guard.adecide("write me a poem")

        assert decision.action == GuardrailAction.BLOCK


class TestSensitivityParsing:
    def test_default_is_medium(self, mock_llm):
        assert ScopeGuard(SCOPE, mock_llm())._sensitivity == ScopeSensitivity.MEDIUM

    @pytest.mark.parametrize(
        "value, expected",
        [
            (ScopeSensitivity.HIGH, ScopeSensitivity.HIGH),
            ("HIGH", ScopeSensitivity.HIGH),
            ("high", ScopeSensitivity.HIGH),
            ("Medium", ScopeSensitivity.MEDIUM),
            ("low", ScopeSensitivity.LOW),
        ],
    )
    def test_accepted_values(self, mock_llm, value, expected):
        guard = ScopeGuard(SCOPE, mock_llm(), sensitivity=value)

        assert guard._sensitivity == expected

    @pytest.mark.parametrize("value", ["EXTREME", "", 2])
    def test_invalid_values_raise(self, mock_llm, value):
        with pytest.raises(ValueError) as exc:
            ScopeGuard(SCOPE, mock_llm(), sensitivity=value)

        for level in ("LOW", "MEDIUM", "HIGH"):
            assert level in str(exc.value)


class TestSensitivityMatrix:
    @pytest.mark.parametrize(
        "sensitivity, label, blocked",
        [
            ("LOW", "IN_SCOPE", False),
            ("LOW", "UNKNOWN", False),
            ("LOW", "OUT_OF_SCOPE", False),
            ("MEDIUM", "IN_SCOPE", False),
            ("MEDIUM", "UNKNOWN", False),
            ("MEDIUM", "OUT_OF_SCOPE", True),
            ("HIGH", "IN_SCOPE", False),
            ("HIGH", "UNKNOWN", True),
            ("HIGH", "OUT_OF_SCOPE", True),
        ],
    )
    async def test_matrix(self, mock_llm, sensitivity, label, blocked):
        guard, _ = _make_guard(mock_llm, label=label, sensitivity=sensitivity)

        decision = await guard.adecide("some request")

        expected = GuardrailAction.BLOCK if blocked else GuardrailAction.ALLOW
        assert decision.action == expected
        if blocked:
            assert (
                decision.user_facing_message
                == scope_module._USER_FACING_MESSAGES[scope_module._ScopeLabel(label)]
            )
            assert decision.meta["label"] == label


class TestBlock:
    async def test_out_of_scope(self, mock_llm):
        guard, _ = _make_guard(mock_llm, label="OUT_OF_SCOPE", sensitivity="MEDIUM")

        decision = await guard.adecide("write a poem about the sea")

        assert decision.action == GuardrailAction.BLOCK
        assert (
            decision.reason
            == scope_module._BLOCK_REASONS[scope_module._ScopeLabel.OUT_OF_SCOPE]
        )
        assert SCOPE not in decision.reason
        assert "judge reason" not in decision.reason
        assert decision.user_facing_message == (
            "Sorry, I can only help with topics this assistant covers. "
            "Feel free to ask something related."
        )
        assert decision.meta == {
            "label": "OUT_OF_SCOPE",
            "sensitivity": "MEDIUM",
            "judge_reason": "judge reason",
        }
        assert all(isinstance(v, str) for v in decision.meta.values())

    async def test_unknown_under_high(self, mock_llm):
        guard, _ = _make_guard(mock_llm, label="UNKNOWN", sensitivity="HIGH")

        decision = await guard.adecide("help me with this")

        assert decision.action == GuardrailAction.BLOCK
        assert (
            decision.reason
            == scope_module._BLOCK_REASONS[scope_module._ScopeLabel.UNKNOWN]
        )
        assert decision.user_facing_message == (
            "Could you tell me a bit more about what you need help with?"
        )
        assert "outside" not in decision.user_facing_message


class TestAllow:
    async def test_in_scope(self, mock_llm):
        guard, _ = _make_guard(mock_llm, label="IN_SCOPE")

        decision = await guard.adecide("why was I charged twice?")

        assert decision.action == GuardrailAction.ALLOW
        assert decision.reason == scope_module._ALLOW_REASON
        assert decision.meta["label"] == "IN_SCOPE"
        assert decision.meta["sensitivity"] == "MEDIUM"
        assert decision.meta["judge_reason"] == "judge reason"

    async def test_low_is_observation_mode(self, mock_llm):
        guard, seen = _make_guard(mock_llm, label="OUT_OF_SCOPE", sensitivity="LOW")

        decision = await guard.adecide("write a poem about the sea")

        assert decision.action == GuardrailAction.ALLOW
        assert decision.meta["label"] == "OUT_OF_SCOPE"
        assert len(seen["calls"]) == 1

    async def test_unknown_under_medium(self, mock_llm):
        guard, _ = _make_guard(mock_llm, label="UNKNOWN", sensitivity="MEDIUM")

        decision = await guard.adecide("help me with this")

        assert decision.action == GuardrailAction.ALLOW


class TestSkipJudge:
    async def test_tool_loop_continuation(self, mock_llm):
        guard, seen = _make_guard(mock_llm, label="OUT_OF_SCOPE")
        tool_result = rt.llm.ToolResponse(identifier="1", result="done", name="lookup")
        history = MessageHistory(
            [
                UserMessage("write a poem"),
                AssistantMessage(
                    [rt.llm.ToolCall(identifier="1", name="lookup", arguments={})]
                ),
                ToolMessage(tool_result),
            ]
        )

        decision = await guard.adecide(history)

        assert decision.action == GuardrailAction.ALLOW
        assert decision.reason == scope_module._TOOL_LOOP_REASON
        assert seen["calls"] == []

    async def test_only_system_message(self, mock_llm):
        guard, seen = _make_guard(mock_llm, label="OUT_OF_SCOPE")

        decision = await guard.adecide(MessageHistory([SystemMessage("be helpful")]))

        assert decision.action == GuardrailAction.ALLOW
        assert decision.reason == scope_module._NO_USER_TEXT_REASON
        assert seen["calls"] == []

    @pytest.mark.parametrize("text", ["", "  \n "])
    async def test_blank_user_message(self, mock_llm, text):
        guard, seen = _make_guard(mock_llm, label="OUT_OF_SCOPE")

        decision = await guard.adecide(text)

        assert decision.action == GuardrailAction.ALLOW
        assert decision.reason == scope_module._NO_USER_TEXT_REASON
        assert seen["calls"] == []

    async def test_trailing_assistant_message_still_judged(self, mock_llm):
        guard, seen = _make_guard(mock_llm, label="OUT_OF_SCOPE")
        history = MessageHistory(
            [UserMessage("write a poem"), AssistantMessage("Sure, here you go")]
        )

        decision = await guard.adecide(history)

        assert decision.action == GuardrailAction.BLOCK
        assert len(seen["calls"]) == 1


class TestJudgeInput:
    async def test_guarded_system_message_not_sent(self, mock_llm):
        guard, seen = _make_guard(mock_llm)
        history = MessageHistory(
            [SystemMessage("SECRET GUARDED PROMPT"), UserMessage("hello")]
        )

        await guard.adecide(history)

        sent = " ".join(str(m.content) for m in seen["calls"][0])
        assert "SECRET GUARDED PROMPT" not in sent

    async def test_system_message_identical_across_sensitivities(self, mock_llm):
        prompts = []
        for sensitivity in ("LOW", "MEDIUM", "HIGH"):
            guard, seen = _make_guard(mock_llm, sensitivity=sensitivity)
            await guard.adecide("hello")
            prompts.append(_judge_system_text(seen))

        assert prompts[0] == prompts[1] == prompts[2]
        assert "sensitivity" not in prompts[0].lower()

    async def test_scope_wrapped_in_tag(self, mock_llm):
        guard, seen = _make_guard(mock_llm)

        await guard.adecide("hello")

        assert f"<scope>\n{SCOPE}\n</scope>" in _judge_system_text(seen)

    async def test_context_window_is_last_four_in_order(self, mock_llm):
        guard, seen = _make_guard(mock_llm)
        earlier = []
        for i in range(3):
            earlier += [UserMessage(f"user-{i}"), AssistantMessage(f"assistant-{i}")]
        history = MessageHistory([*earlier, UserMessage("latest question")])

        await guard.adecide(history)

        text = _judge_user_text(seen)
        for kept in ("user-1", "assistant-1", "user-2", "assistant-2"):
            assert kept in text
        for dropped in ("user-0", "assistant-0"):
            assert dropped not in text
        assert text.index("user-1") < text.index("assistant-1") < text.index("user-2")
        latest_block = text.split("<latest_user_message>")[1].split(
            "</latest_user_message>"
        )[0]
        assert "latest question" in latest_block
        assert "latest question" not in text.split("<latest_user_message>")[0]

    async def test_tool_and_tool_call_messages_excluded_from_context(self, mock_llm):
        guard, seen = _make_guard(mock_llm)
        history = MessageHistory(
            [
                UserMessage("first question"),
                AssistantMessage(
                    [rt.llm.ToolCall(identifier="1", name="lookup_tool", arguments={})]
                ),
                ToolMessage(
                    rt.llm.ToolResponse(
                        identifier="1", result="TOOL RESULT", name="lookup_tool"
                    )
                ),
                AssistantMessage("answer"),
                UserMessage("follow up"),
            ]
        )

        await guard.adecide(history)

        text = _judge_user_text(seen)
        assert "lookup_tool" not in text
        assert "TOOL RESULT" not in text
        assert "first question" in text
        assert "answer" in text

    async def test_truncation_applies_to_context_only(self, mock_llm):
        guard, seen = _make_guard(mock_llm)
        limit = scope_module._CONTEXT_CHAR_LIMIT
        history = MessageHistory(
            [
                UserMessage("a" * (limit + 100)),
                AssistantMessage("ok"),
                UserMessage("b" * (limit + 100)),
            ]
        )

        await guard.adecide(history)

        text = _judge_user_text(seen)
        assert "a" * limit in text
        assert "a" * (limit + 1) not in text
        assert "b" * (limit + 100) in text

    async def test_single_message_has_only_latest_block(self, mock_llm):
        guard, seen = _make_guard(mock_llm)

        await guard.adecide("just one message")

        text = _judge_user_text(seen)
        assert "earlier_conversation" not in text
        assert text.startswith("<latest_user_message>")
        assert "just one message" in text


class TestJudgeFailure:
    """``adecide`` bypasses ``run``/``fail_open``, so failures go through ``run``."""

    @staticmethod
    def _run(guard, text="hello"):
        history = MessageHistory([UserMessage(text)])
        return guard.run(event=_input_event(history), value=history)

    async def test_judge_exception_fails_open(self, mock_llm):
        llm = mock_llm()

        def boom(messages, schema, **kwargs):
            raise RuntimeError("judge down")

        llm._structured = boom  # type: ignore[method-assign]
        guard = ScopeGuard(SCOPE, llm)

        _, traces, decision = await self._run(guard)

        assert decision.action == GuardrailAction.ALLOW
        assert traces[-1].action == "error"
        assert traces[-1].meta["exception_type"] == "LLMError"

    async def test_fail_open_false_blocks_on_judge_error(self, mock_llm):
        llm = mock_llm()

        def boom(messages, schema, **kwargs):
            raise RuntimeError("judge down")

        llm._structured = boom  # type: ignore[method-assign]
        guard = ScopeGuard(SCOPE, llm, fail_open=False)

        _, traces, decision = await self._run(guard)

        assert decision.action == GuardrailAction.BLOCK
        assert traces[-1].action == "error"
        assert traces[-1].meta["exception_type"] == "LLMError"

    @pytest.mark.parametrize("raw", ["out of scope", "Out-Of-Scope", " out_of_scope "])
    async def test_label_spelling_is_normalized(self, mock_llm, raw):
        llm = mock_llm(custom_response=f'{{"reason": "r", "label": "{raw}"}}')
        guard = ScopeGuard(SCOPE, llm)

        _, traces, decision = await self._run(guard)

        assert decision.action == GuardrailAction.BLOCK
        assert traces[-1].meta["label"] == "OUT_OF_SCOPE"

    async def test_invalid_label_fails_open(self, mock_llm):
        llm = mock_llm(custom_response='{"reason": "r", "label": "RELATED"}')
        guard = ScopeGuard(SCOPE, llm)

        _, traces, decision = await self._run(guard)

        assert decision.action == GuardrailAction.ALLOW
        assert traces[-1].action == "error"

    async def test_adecide_raises_judge_error(self, mock_llm):
        llm = mock_llm()

        def boom(messages, schema, **kwargs):
            raise RuntimeError("judge down")

        llm._structured = boom  # type: ignore[method-assign]
        guard = ScopeGuard(SCOPE, llm)

        with pytest.raises(LLMError):
            await guard.adecide("hello")


class TestGuardName:
    async def test_names(self, mock_llm):
        guard, _ = _make_guard(mock_llm, label="OUT_OF_SCOPE")
        history = MessageHistory([UserMessage("write a poem")])

        _, traces, _ = await guard.run(event=_input_event(history), value=history)

        assert guard.name == "ScopeGuard"
        assert traces[-1].rail_name == "ScopeGuard"
        assert guard._judge.name() == "ScopeGuard-judge"

    async def test_custom_name(self, mock_llm):
        llm, _ = _judge_llm(mock_llm, "OUT_OF_SCOPE")
        guard = ScopeGuard(SCOPE, llm, name="bakery-scope")
        history = MessageHistory([UserMessage("write a poem")])

        _, traces, _ = await guard.run(event=_input_event(history), value=history)

        assert guard.name == "bakery-scope"
        assert traces[-1].rail_name == "bakery-scope"
        assert guard._judge.name() == "bakery-scope-judge"


class TestDecide:
    def test_sync_decide_raises_type_error(self, mock_llm):
        guard, _ = _make_guard(mock_llm)

        with pytest.raises(TypeError):
            guard.decide("hello")


class TestConcurrency:
    async def test_concurrent_calls_share_one_instance(self, mock_llm):
        guard, seen = _make_guard(mock_llm, label="OUT_OF_SCOPE")

        first, second = await asyncio.gather(guard.adecide("one"), guard.adecide("two"))

        assert first.action == GuardrailAction.BLOCK
        assert second.action == GuardrailAction.BLOCK
        assert len(seen["calls"]) == 2
