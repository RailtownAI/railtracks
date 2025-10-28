import railtracks as rt
from railtracks.llm.message import Message, Role


def test_message_history_str(message_history):
    """
    Test the __str__ method of MessageHistory.
    """
    # Add mock messages to the history
    message1 = Message(role=Role.user, content="Hello")
    message2 = Message(role=Role.assistant, content="Hi there!")
    message_history.extend([message1, message2])

    # Check the string representation
    expected_str = "user: Hello\nassistant: Hi there!"
    assert str(message_history) == expected_str


def test_message_hist_string():
    message_hist = rt.llm.MessageHistory(
        [rt.llm.UserMessage("What is going on in this beautiful world?")]
    )

    assert str(message_hist) == "user: What is going on in this beautiful world?"


def test_multiline_hist_string():
    message_hist = rt.llm.MessageHistory(
        [
            rt.llm.UserMessage("What is going on in this beautiful world?"),
            rt.llm.AssistantMessage("Nothing much as of now"),
        ]
    )

    assert (
        str(message_hist)
        == "user: What is going on in this beautiful world?\nassistant: Nothing much as of now"
    )
