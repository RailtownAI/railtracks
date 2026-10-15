import io
import sys

import pytest
from railtracks.exceptions._base import RTError, _stderr_is_terminal
from railtracks.exceptions.errors import (
    ContextError,
    FatalError,
    GlobalTimeOutError,
    LLMError,
    NodeCreationError,
    NodeInvocationError,
)

# NOTE: This file contains very basic tests to ensure that the exception classes are working as expected.


class _Stderr(io.StringIO):
    def __init__(self, tty: bool):
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


# pytest swaps sys.stderr for its own capture before each test runs, so the fixtures
# decide the terminal check itself
@pytest.fixture
def terminal(monkeypatch):
    """Stderr is a terminal, where RT errors are coloured."""
    monkeypatch.setattr("railtracks.exceptions._base._stderr_is_terminal", lambda: True)


@pytest.fixture
def redirected(monkeypatch):
    """Stderr goes to a file or pipe, where colour codes would only be noise."""
    monkeypatch.setattr(
        "railtracks.exceptions._base._stderr_is_terminal", lambda: False
    )


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [(_Stderr(tty=True), True), (_Stderr(tty=False), False), (None, False)],
)
def test_stderr_counts_as_a_terminal_only_when_it_is_one(monkeypatch, stderr, expected):
    monkeypatch.setattr(sys, "stderr", stderr)
    assert _stderr_is_terminal() is expected


# =========== START RTError utility tests ===========
@pytest.mark.parametrize(
    "text,color_code,expected",
    [
        ("hello", RTError.RED, f"{RTError.RED}hello{RTError.RESET}"),
        ("world", RTError.GREEN, f"{RTError.GREEN}world{RTError.RESET}"),
    ],
)
def test_rcerror_color_helper(terminal, text, color_code, expected):
    assert RTError._color(text, color_code) == expected


def test_errors_are_plain_when_stderr_is_redirected(redirected):
    assert RTError._color("hello", RTError.RED) == "hello"
    assert str(GlobalTimeOutError(12.3)) == "Execution timed out after 12.3 seconds"
    assert "\033[" not in str(NodeInvocationError("fail", notes=["check x"]))
    assert "\033[" not in str(LLMError("bad response"))


# ========== END RTError utility tests ==============


# =========== START NodeInvocationError tests =======
def test_nodeinvocationerror_basic(terminal):
    err = NodeInvocationError("fail occurred")
    assert err.fatal is False
    assert err.notes == []
    assert "fail occurred" in str(err)
    assert "\033[" in str(err)  # Should be colored


def test_nodeinvocationerror_with_notes_and_fatal():
    err = NodeInvocationError(
        "exec crashed", notes=["check y", "try again"], fatal=True
    )
    s = str(err)
    assert "exec crashed" in s
    for note in err.notes:
        assert note in s
    assert "Tips to debug:" in s
    assert err.fatal is True


# ========== END NodeInvocationError tests ===========


# =========== START NodeCreationError tests =======
def test_nodecreationerror_default_message():
    err = NodeCreationError()
    assert "Something went wrong" in str(err)


def test_nodecreationerror_with_notes():
    notes = ["Check configuration", "Missing parameter"]
    err = NodeCreationError("Custom msg", notes=notes)
    s = str(err)
    assert "Custom msg" in s and "Tips to debug" in s
    for note in notes:
        assert note in s


# ========== END NodeCreationError tests ===========


# =========== START LLMError tests =================
@pytest.fixture
def fake_message_history():
    class Fake:
        def __str__(self):
            return "FakeHistory\nLine2"

        def __len__(self):
            return 2

    return Fake()


def test_llmerror_basic():
    err = LLMError("api failed")
    s = str(err)
    assert "LLM Error" in s
    assert "api failed" in s


def test_llmerror_redacts_history_by_default(fake_message_history):
    err = LLMError("timeout!", message_history=fake_message_history)
    s = str(err)
    assert "timeout!" in s
    assert "Message History" in s
    assert "2 message(s) redacted" in s
    assert "FakeHistory" not in s
    assert "Line2" not in s
    # Attribute is preserved for opt-in access
    assert err.message_history is fake_message_history


def test_llmerror_format_verbose_includes_history(fake_message_history):
    err = LLMError("timeout!", message_history=fake_message_history)
    s = err.format_verbose()
    assert "timeout!" in s
    assert "Message History:" in s
    assert "FakeHistory" in s
    assert "Line2" in s


def test_llmerror_format_verbose_without_history():
    err = LLMError("api failed")
    assert err.format_verbose() == str(err)


# =========== END LLMError tests ===================


# =========== START GlobalTimeOutError tests =======
def test_globaltimeout_basic(terminal):
    err = GlobalTimeOutError(12.3)
    s = str(err)
    assert "12.3" in s
    assert "timed out" in s
    assert "\033[" in s  # colored output


# =========== END GlobalTimeOutError tests ==========


# =========== START ContextError tests =============
def test_contexterror_defaults():
    err = ContextError()
    s = str(err)
    assert "Context error" in s


def test_contexterror_with_notes():
    err = ContextError("Problem!", notes=["try something"])
    s = str(err)
    assert "Problem!" in s
    assert "try something" in s
    assert "Tips to debug" in s


# =========== END ContextError tests ===============


# =========== START FatalError tests ===============
def test_fatalerror_is_rcerror():
    err = FatalError("boom")
    assert isinstance(err, RTError)
    assert str(err) == "boom" or "boom" in str(err)


@pytest.mark.parametrize(
    "exc,expected",
    [
        (FatalError("boom"), True),
        (NodeInvocationError("bad config", fatal=True), True),
        (NodeInvocationError("bad config"), False),
        (ContextError("missing key"), False),
    ],
)
def test_fatal_marks_only_errors_that_stop_the_run(exc, expected):
    assert exc.fatal is expected


# =========== END FatalError tests =================
