import pytest
import railtracks as rt

from railtracks.built_nodes.concrete.rag import (
    _prepare_messages,
    _random_contiguous_subsequence,
    _parse_message_combos,
    update_context,
)


# ---------------------------------------------------------
# Fixtures for simple railtracks messages
# ---------------------------------------------------------
@pytest.fixture
def user_msg():
    return rt.llm.UserMessage("user_text")

@pytest.fixture
def assistant_msg():
    return rt.llm.AssistantMessage("assistant_text")

@pytest.fixture
def another_user_msg():
    return rt.llm.UserMessage("user2")

@pytest.fixture
def another_assistant_msg():
    return rt.llm.AssistantMessage("assistant2")


# ---------------------------------------------------------
# _prepare_messages
# ---------------------------------------------------------
def test_prepare_messages_single(user_msg):
    assert _prepare_messages(user_msg) == str(user_msg)

def test_prepare_messages_list(user_msg, assistant_msg):
    out = _prepare_messages([user_msg, assistant_msg])
    assert out == f"{user_msg}\n{assistant_msg}"


# ---------------------------------------------------------
# _random_contiguous_subsequence
# ---------------------------------------------------------
def test_random_contiguous_subsequence_basic():
    seq = [("U1", "A1"), ("U2", "A2")]
    out = _random_contiguous_subsequence(seq)

    assert out == [
        "U1\nA1",
        "U1\nA1\nU2\nA2",
        "U2\nA2",
    ]


# ---------------------------------------------------------
# _parse_message_combos
# ---------------------------------------------------------
def test_parse_message_combos_simple(user_msg, assistant_msg):
    history = rt.llm.MessageHistory([user_msg, assistant_msg])
    out = _parse_message_combos(history)

    # Should group as (user_message_str, assistant_messages_str)
    assert len(out) == 1
    assert out[0][0] == str(user_msg)
    assert out[0][1] == str(assistant_msg)


def test_parse_message_combos_multiple_groups(
    user_msg, assistant_msg, another_user_msg, another_assistant_msg
):
    history = rt.llm.MessageHistory([
        user_msg,
        assistant_msg,
        another_user_msg,
        another_assistant_msg,
    ])

    out = _parse_message_combos(history)

    assert len(out) == 2

    # Group 1
    assert out[0][0] == str(user_msg)
    assert out[0][1] == str(assistant_msg)

    # Group 2
    assert out[1][0] == str(another_user_msg)
    assert out[1][1] == str(another_assistant_msg)


def test_parse_message_combos_skips_system_messages(user_msg, assistant_msg):
    system = rt.llm.SystemMessage("sys")
    history = rt.llm.MessageHistory([system, user_msg, assistant_msg])

    out = _parse_message_combos(history)

    assert len(out) == 1
    assert out[0][0] == str(user_msg)


def test_parse_message_combos_raises_if_not_starting_with_user(assistant_msg):
    history = rt.llm.MessageHistory([assistant_msg])
    with pytest.raises(AssertionError):
        _parse_message_combos(history)


# ---------------------------------------------------------
# update_context
# ---------------------------------------------------------
def test_update_context_inserts_new_message(user_msg, assistant_msg, mock_vector_store):
    """
    Ensures the update_context function prepends a new user message
    containing injected context.
    """
    # Setup vector store to return fake results
    def fake_search(query, top_k, **kwargs):
        class FakeItem:
            def __init__(self, id, content):
                self.id = id
                self.content = content

        return [
            FakeItem("1", "CTX-A"),
            FakeItem("2", "CTX-B"),
        ]

    mock_vector_store._custom_search = fake_search

    history = rt.llm.MessageHistory([user_msg, assistant_msg])
    out = update_context(history, mock_vector_store, top_k=1)

    # New message should be inserted at index 0
    assert len(out) == 3
    injected = out[0]

    assert isinstance(injected, rt.llm.UserMessage)
    assert "You may find the following useful:" in injected.content
    assert "CTX-A" in injected.content
    assert "CTX-B" in injected.content


def test_update_context_does_not_modify_original_history(
    user_msg, assistant_msg, mock_vector_store
):
    mock_vector_store._custom_search = lambda q, top_k, **_: []

    history = rt.llm.MessageHistory([user_msg, assistant_msg])
    original_copy = list(history)

    _ = update_context(history, mock_vector_store)

    # Original must be unchanged
    assert list(history) == original_copy


def test_update_context_handles_duplicate_results(
    user_msg, assistant_msg, mock_vector_store
):
    """Duplicates should be removed based on item.id."""

    class FakeItem:
        def __init__(self, id, content):
            self.id = id
            self.content = content

    def fake_search(query, top_k, **kwargs):
        return [
            FakeItem("1", "CTX"),
            FakeItem("1", "CTX-SHOULD-NOT-DUPLICATE"),
        ]

    mock_vector_store._custom_search = fake_search

    history = rt.llm.MessageHistory([user_msg, assistant_msg])
    out = update_context(history, mock_vector_store)

    injected = out[0].content
    assert injected.count("CTX") == 1


def test_update_context_handles_nested_lists(
    user_msg, assistant_msg, mock_vector_store
):
    """Search may return lists of results."""

    class FakeItem:
        def __init__(self, id, content):
            self.id = id
            self.content = content

    def fake_search(query, top_k, **kwargs):
        return [
            [FakeItem("A", "X"), FakeItem("B", "Y")],
            FakeItem("C", "Z"),
        ]

    mock_vector_store._custom_search = fake_search

    history = rt.llm.MessageHistory([user_msg, assistant_msg])
    out = update_context(history, mock_vector_store)

    text = out[0].content

    assert "X" in text
    assert "Y" in text
    assert "Z" in text


# ---------------------------------------------------------
# Optional: ensure valid text separator formatting
# ---------------------------------------------------------
def test_update_context_separator_format(
    user_msg, assistant_msg, mock_vector_store
):
    mock_vector_store._custom_search = lambda q, top_k, **_: []

    history = rt.llm.MessageHistory([user_msg, assistant_msg])
    out = update_context(history, mock_vector_store)

    injected = out[0].content
    assert "You may find the following useful:" in injected
