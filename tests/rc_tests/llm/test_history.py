import pytest
from src.requestcompletion.llm.message import Message
from src.requestcompletion.llm.history import MessageHistory


def test_message_history_is_valid(message_history):
    """
    Test the is_valid method of MessageHistory.
    """
    assert message_history.is_valid() is True


def test_message_history_str(message_history):
    """
    Test the __str__ method of MessageHistory.
    """
    # Add mock messages to the history
    message1 = Message(role="user", content="Hello")
    message2 = Message(role="assistant", content="Hi there!")
    message_history.extend([message1, message2])

    # Check the string representation
    expected_str = "user: Hello\nassistant: Hi there!"
    assert str(message_history) == expected_str


def test_empty_message_history():
    empty_history = MessageHistory()
    assert str(empty_history) == ""
    assert empty_history.is_valid() is True

