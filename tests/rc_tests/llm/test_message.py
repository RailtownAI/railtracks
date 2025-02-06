import pytest
from requestcompletion.llm import UserMessage


def test_user_message():
    message = UserMessage("Hello")
    assert message.content == "Hello"
    assert message.role == "user"
    assert str(message) == "user: Hello"
    assert repr(message) == "user: Hello"


def test_bad_input_message():
    with pytest.raises(TypeError) as e:
        UserMessage(1)  # noqa

    assert e.type == TypeError
