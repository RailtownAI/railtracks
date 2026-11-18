from __future__ import annotations

import warnings

import pytest
from railtracks.utils.deprecation import (
    NEXT_VERSION,
    UPGRADE_GUIDE,
    renamed_argument,
    warn_pending_change,
)


def test_warn_pending_change_defaults_to_next_version():
    with pytest.warns(FutureWarning, match=f"railtracks {NEXT_VERSION}"):
        warn_pending_change("thing")


def test_warn_pending_change_names_given_version():
    with pytest.warns(FutureWarning) as record:
        warn_pending_change("thing", change="is removed", version="2.0.0")

    message = str(record[0].message)
    assert "thing is removed in railtracks 2.0.0." in message
    assert NEXT_VERSION not in message


def test_warn_pending_change_links_the_upgrade_guide_by_default():
    with pytest.warns(FutureWarning) as record:
        warn_pending_change("thing")

    assert UPGRADE_GUIDE in str(record[0].message)


def test_warn_pending_change_links_given_guide():
    guide = "https://docs.example.org/renames/"
    with pytest.warns(FutureWarning) as record:
        warn_pending_change("thing", version="2.0.0", guide=guide)

    message = str(record[0].message)
    assert guide in message
    assert UPGRADE_GUIDE not in message


class _Widget:
    def __init__(self, new: str | None = None, *, old: str | None = None) -> None:
        self.value = renamed_argument(
            "_Widget",
            old="old",
            new="new",
            old_value=old,
            new_value=new,
            version="2.0.0",
        )


def test_renamed_argument_returns_new_value_silently():
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        assert _Widget(new="x").value == "x"


def test_renamed_argument_returns_old_value_with_warning():
    with pytest.warns(FutureWarning) as record:
        widget = _Widget(old="x")

    assert widget.value == "x"
    message = str(record[0].message)
    assert "_Widget(old=...)" in message
    assert "2.0.0" in message
    assert "Use new= instead." in message


def test_renamed_argument_warning_points_at_the_caller():
    with pytest.warns(FutureWarning) as record:
        _Widget(old="x")

    assert record[0].filename == __file__


def test_renamed_argument_rejects_both_names():
    with pytest.raises(TypeError, match="old.*new"):
        _Widget(new="x", old="y")


def test_renamed_argument_treats_new_default_as_unset():
    with pytest.warns(FutureWarning):
        value = renamed_argument(
            "Thing",
            old="old",
            new="new",
            old_value="y",
            new_value="*",
            unset="*",
            stacklevel=3,
        )

    assert value == "y"


def test_renamed_argument_passes_guide_through():
    guide = "https://docs.example.org/renames/"
    with pytest.warns(FutureWarning) as record:
        renamed_argument(
            "Thing",
            old="old",
            new="new",
            old_value="y",
            new_value=None,
            guide=guide,
            stacklevel=3,
        )

    message = str(record[0].message)
    assert guide in message
    assert UPGRADE_GUIDE not in message
