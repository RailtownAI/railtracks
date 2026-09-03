import pytest
from railtracks.llm.models._model_exception_base import ModelError


@pytest.fixture
def fake_message_history():
    class Fake:
        def __str__(self):
            return "FakeHistory\nLine2"

        def __len__(self):
            return 2

    return Fake()


def test_modelerror_basic():
    err = ModelError("api failed")
    s = str(err)
    assert "Failure reason" in s
    assert "api failed" in s


def test_modelerror_redacts_history_by_default(fake_message_history):
    err = ModelError("timeout!", message_history=fake_message_history)
    s = str(err)
    assert "timeout!" in s
    assert "Message History" in s
    assert "2 message(s) redacted" in s
    assert "FakeHistory" not in s
    assert "Line2" not in s
    assert err.message_history is fake_message_history


def test_modelerror_format_verbose_includes_history(fake_message_history):
    err = ModelError("timeout!", message_history=fake_message_history)
    s = err.format_verbose()
    assert "timeout!" in s
    assert "Message History:" in s
    assert "FakeHistory" in s
    assert "Line2" in s


def test_modelerror_format_verbose_without_history():
    err = ModelError("api failed")
    assert err.format_verbose() == str(err)
