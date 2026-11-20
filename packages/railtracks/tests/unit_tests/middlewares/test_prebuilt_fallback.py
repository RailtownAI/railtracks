"""Unit tests for the prebuilt Fallback middleware: `rt.prebuilt.middleware.Fallback`.

Fallback is node-level — it hands the input to backup nodes through `rt.call`
when the wrapped call raises an `on` error — so the tests run the full path
through `rt.Flow` rather than wiring `.wrap(fake_call)` directly.
"""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.exceptions.errors import LLMError
from railtracks.middleware import Middleware
from railtracks.prebuilt.middleware import Fallback


def test_fallback_is_a_plain_middleware():
    @rt.function_node
    def backup() -> str:
        """Always succeeds."""
        return "backup"

    assert isinstance(Fallback(backup), Middleware)


def test_constructor_requires_at_least_one_backup():
    with pytest.raises(ValueError, match="at least one backup"):
        Fallback()


def test_constructor_rejects_non_node_backups():
    with pytest.raises(TypeError, match="must be nodes"):
        Fallback("not a node")


def test_primary_result_passes_through_without_touching_backups():
    backup_calls = []

    @rt.function_node
    def backup(x: int) -> int:
        """Backup identity."""
        backup_calls.append(x)
        return x + 100

    @rt.function_node(middleware=[Fallback(backup)])
    def primary(x: int) -> int:
        """Primary identity."""
        return x * 2

    assert rt.Flow("test_fallback_passthrough", primary).invoke(5) == 10
    assert backup_calls == []


def test_llm_error_falls_back_to_backup_with_same_input():
    backup_calls = []

    @rt.function_node
    def backup(x: int) -> int:
        """Backup node."""
        backup_calls.append(x)
        return x + 100

    @rt.function_node(middleware=[Fallback(backup)])
    def primary(x: int) -> int:
        """Primary node."""
        raise LLMError(reason="provider down")

    assert rt.Flow("test_fallback_llm_error", primary).invoke(5) == 105
    assert backup_calls == [5]


def test_args_and_kwargs_are_forwarded_to_the_backup():
    seen = {}

    @rt.function_node
    def backup(a: int, b: int, *, tag: str) -> str:
        """Backup echo."""
        seen.update(a=a, b=b, tag=tag)
        return tag

    @rt.function_node(middleware=[Fallback(backup)])
    def primary(a: int, b: int, *, tag: str) -> str:
        """Primary that fails."""
        raise LLMError(reason="primary down")

    assert rt.Flow("test_fallback_forwards_args", primary).invoke(1, 2, tag="x") == "x"
    assert seen == {"a": 1, "b": 2, "tag": "x"}


def test_backups_are_tried_in_order():
    attempts = []

    @rt.function_node
    def first_backup() -> str:
        """First backup, also down."""
        attempts.append("first")
        raise LLMError(reason="first backup down")

    @rt.function_node
    def second_backup() -> str:
        """Second backup."""
        attempts.append("second")
        return "recovered"

    @rt.function_node(middleware=[Fallback(first_backup, second_backup)])
    def primary() -> str:
        """Primary that fails."""
        attempts.append("primary")
        raise LLMError(reason="primary down")

    assert rt.Flow("test_fallback_order", primary).invoke() == "recovered"
    assert attempts == ["primary", "first", "second"]


def test_all_attempts_failing_raises_the_last_error():
    @rt.function_node
    def backup() -> str:
        """Backup that also fails."""
        raise LLMError(reason="backup down")

    @rt.function_node(middleware=[Fallback(backup)])
    def primary() -> str:
        """Primary that fails."""
        raise LLMError(reason="primary down")

    with pytest.raises(LLMError, match="backup down"):
        rt.Flow("test_fallback_all_fail", primary).invoke()


def test_error_outside_on_propagates_without_fallback():
    backup_calls = []

    @rt.function_node
    def backup() -> str:
        """Backup node."""
        backup_calls.append("called")
        return "backup"

    @rt.function_node(middleware=[Fallback(backup)])
    def primary() -> str:
        """Primary with a bug."""
        raise ValueError("not a model failure")

    with pytest.raises(ValueError, match="not a model failure"):
        rt.Flow("test_fallback_non_matching_error", primary).invoke()
    assert backup_calls == []


def test_custom_on_widens_the_trigger_set():
    @rt.function_node
    def backup() -> str:
        """Backup node."""
        return "recovered"

    @rt.function_node(middleware=[Fallback(backup, on=(ValueError,))])
    def primary() -> str:
        """Primary that raises a widened trigger."""
        raise ValueError("transient in this domain")

    assert rt.Flow("test_fallback_custom_on", primary).invoke() == "recovered"


def test_reentrant_fallback_runs_the_node_without_looping():
    @rt.function_node
    def backup() -> str:
        """Backup that also fails."""
        raise LLMError(reason="backup down")

    fallback = Fallback(backup)
    # Attach the same instance to its own backup — the config that would
    # recurse forever without the re-entry guard.
    backup.node_type._user_middleware.append(fallback)

    @rt.function_node(middleware=[fallback])
    def primary() -> str:
        """Primary that fails."""
        raise LLMError(reason="primary down")

    with pytest.raises(LLMError, match="backup down"):
        rt.Flow("test_fallback_reentry", primary).invoke()
