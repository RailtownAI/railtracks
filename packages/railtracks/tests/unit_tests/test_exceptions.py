import pytest
from railtracks.exceptions.errors import (
    NodeInvocationError,
    NodeCreationError,
    LLMError,
    GlobalTimeOutError,
    ContextError,
    FatalError,
)
from railtracks.exceptions._base import RTError

# NOTE: This file contains very basic tests to ensure that the exception classes are working as expected.


# =========== START RTError utility tests ===========
@pytest.mark.parametrize(
    "text,color_code,expected",
    [
        ("hello", RTError.RED, f"{RTError.RED}hello{RTError.RESET}"),
        ("world", RTError.GREEN, f"{RTError.GREEN}world{RTError.RESET}"),
    ]
)
def test_rcerror_color_helper(text, color_code, expected):
    assert RTError._color(text, color_code) == expected
# ========== END RTError utility tests ==============


# =========== START NodeInvocationError tests =======
def test_nodeinvocationerror_basic():
    err = NodeInvocationError("fail occurred")
    assert err.fatal is False
    assert err.notes == []
    assert "fail occurred" in str(err)
    assert "\033[" in str(err)  # Should be colored

def test_nodeinvocationerror_with_notes_and_fatal():
    err = NodeInvocationError("exec crashed", notes=["check y", "try again"], fatal=True)
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
    return Fake()

def test_llmerror_basic():
    err = LLMError("api failed")
    s = str(err)
    assert "LLM Error" in s
    assert "api failed" in s

def test_llmerror_with_history(fake_message_history):
    err = LLMError("timeout!", message_history=fake_message_history)
    s = str(err)
    assert "timeout!" in s
    assert "Message History:" in s
    assert "FakeHistory" in s
    assert "Line2" in s
# =========== END LLMError tests ===================

# =========== START GlobalTimeOutError tests =======
def test_globaltimeout_basic():
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
# =========== END FatalError tests =================