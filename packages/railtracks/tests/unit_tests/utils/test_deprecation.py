from __future__ import annotations

import inspect
import warnings

import pytest
from railtracks.utils.deprecation import (
    NEXT_VERSION,
    UPGRADE_GUIDE,
    renamed_kwargs,
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


GUIDE = "https://docs.example.org/renames/"


class _Widget:
    @renamed_kwargs(old="new", stale="mode", version="2.0.0", guide=GUIDE)
    def __init__(self, new: str, *, mode: str = "default") -> None:
        self.value = new
        self.mode = mode


def test_renamed_kwargs_new_name_is_silent():
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        assert _Widget(new="x").value == "x"


def test_renamed_kwargs_forwards_old_name_with_warning():
    with pytest.warns(FutureWarning) as record:
        widget = _Widget(old="x")

    assert widget.value == "x"
    message = str(record[0].message)
    assert "_Widget(old=...) is removed in railtracks 2.0.0." in message
    assert "Use new= instead." in message
    assert GUIDE in message
    assert UPGRADE_GUIDE not in message


def test_renamed_kwargs_warning_points_at_the_calling_line():
    with pytest.warns(FutureWarning) as record:
        line = inspect.currentframe().f_lineno + 1
        _Widget(old="x")

    assert record[0].filename == __file__
    assert record[0].lineno == line


def test_renamed_kwargs_rejects_both_names_by_keyword():
    with pytest.raises(TypeError, match=r"_Widget\(\) got both old= and new="):
        _Widget(new="x", old="y")


def test_renamed_kwargs_rejects_old_name_with_new_name_by_position():
    with pytest.raises(TypeError, match="old=.*new="):
        _Widget("x", old="y")


def test_renamed_kwargs_rejects_both_names_when_new_is_at_its_default():
    with pytest.raises(TypeError, match="stale=.*mode="):
        _Widget("x", mode="default", stale="other")


def test_renamed_kwargs_keeps_required_arguments_required():
    with pytest.raises(TypeError, match="new"):
        _Widget()


def test_renamed_kwargs_handles_each_rename_independently():
    with pytest.warns(FutureWarning) as record:
        widget = _Widget(old="x", stale="other")

    assert (widget.value, widget.mode) == ("x", "other")
    assert len(record) == 2


def test_renamed_kwargs_defaults_to_next_version_and_upgrade_guide():
    @renamed_kwargs(before="after")
    def func(*, after: int) -> int:
        return after

    with pytest.warns(FutureWarning) as record:
        assert func(before=1) == 1

    message = str(record[0].message)
    assert f"railtracks {NEXT_VERSION}" in message
    assert UPGRADE_GUIDE in message
