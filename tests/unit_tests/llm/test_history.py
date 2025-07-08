import requestcompletion as rc
from requestcompletion.llm.message import Message


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


def test_message_hist_string():
    message_hist = rc.llm.MessageHistory(
        [rc.llm.UserMessage("What is going on in this beautiful world?")]
    )

    assert str(message_hist) == "user: What is going on in this beautiful world?"


def test_multiline_hist_string():
    message_hist = rc.llm.MessageHistory(
        [
            rc.llm.UserMessage("What is going on in this beautiful world?"),
            rc.llm.AssistantMessage("Nothing much as of now"),
        ]
    )

    assert (
        str(message_hist)
        == "user: What is going on in this beautiful world?\nassistant: Nothing much as of now"
    )
