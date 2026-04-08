"""Tests for GuardrailBlockedError."""

from __future__ import annotations

from railtracks.guardrails.core import GuardrailBlockedError, GuardrailTrace


def test_guardrail_blocked_error_message_and_fields():
    traces = [
        GuardrailTrace(
            rail_name="R1",
            phase="llm_input",
            action="block",
            reason="no",
            meta=None,
        )
    ]
    err = GuardrailBlockedError(
        rail_name="R1",
        reason="policy",
        user_facing_message="try again",
        traces=traces,
        meta={"k": 1},
    )
    assert err.rail_name == "R1"
    assert err.reason == "policy"
    assert err.user_facing_message == "try again"
    assert err.traces == traces
    assert err.meta == {"k": 1}
    assert "Blocked by guardrails" in str(err)
    assert "R1" in str(err)
    assert "policy" in str(err)
