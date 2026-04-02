"""Tests for Guard configuration validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from railtracks.guardrails.core import Guard


def test_guard_empty_lists():
    g = Guard()
    assert g.input == []
    assert g.output == []
    assert g.fail_open is False


def test_guard_rejects_non_callable_input():
    with pytest.raises(ValidationError):
        Guard(input=[object()])  # type: ignore[list-item]


def test_guard_rejects_non_callable_output():
    with pytest.raises(ValidationError):
        Guard(output=[123])  # type: ignore[list-item]
