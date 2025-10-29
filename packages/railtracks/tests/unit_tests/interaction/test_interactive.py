import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from railtracks import interactive
from railtracks.built_nodes.concrete._llm_base import LLMBase
from railtracks.built_nodes.concrete.response import LLMResponse
from railtracks.human_in_the_loop import ChatUI, HILMessage
from railtracks.human_in_the_loop.local_chat_ui import UIUserMessage, UserMessageAttachment
from railtracks.interaction.interactive import _process_attachment
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import UserMessage, AssistantMessage
from railtracks.nodes.nodes import Node


class MockLLMNode(LLMBase):
    """Mock LLM node for testing."""
    pass


@pytest.fixture
def mock_chat_ui_instance() -> AsyncMock:
    """Provides a fully mocked instance of the ChatUI."""
    return AsyncMock(spec=ChatUI)


@pytest.fixture
def mock_chat_ui_class(mock_chat_ui_instance: AsyncMock) -> MagicMock:
    """Provides a mock CLASS that returns the pre-configured instance."""
    mock_class = MagicMock(spec=ChatUI)
    mock_class.__name__ = "ChatUI"
    mock_class.return_value = mock_chat_ui_instance
    return mock_class


def setup_mock_chat_ui(mock_instance: AsyncMock, messages: list[UIUserMessage], connected_states: list[bool]) -> None:
    """Helper to configure mock ChatUI behavior.
    
    Args:
        mock_instance: The ChatUI mock instance to configure
        messages: List of messages to return from receive_message calls
        connected_states: List of connection states for is_connected property
    """
    type(mock_instance).is_connected = PropertyMock(side_effect=connected_states)
    if messages:
        mock_instance.receive_message.side_effect = messages


def create_mock_response(user_content: str, agent_content: str, attachments: list[str] | None = None) -> LLMResponse:
    """Helper to create a mock LLM response with message history.
    
    Args:
        user_content: Content of the user message
        agent_content: Content of the agent response
        attachments: Optional list of attachment URLs/data
        
    Returns:
        An LLMResponse with appropriate message history
    """
    user_msg = UserMessage(user_content, attachment=attachments or [])
    assistant_msg = AssistantMessage(agent_content)
    return LLMResponse(
        content=agent_content,
        message_history=MessageHistory([user_msg, assistant_msg])
    )


# ---- Node Validation Tests ----


@pytest.mark.asyncio
async def test_interactive_with_invalid_node():
    """Verifies that local_chat raises ValueError for non-LLMBase nodes."""
    class InvalidNode(Node):
        pass

    with pytest.raises(
        ValueError,
        match="Interactive sessions only support nodes that are children of LLMBase.",
    ):
        await interactive.local_chat(node=InvalidNode)


# ---- Core Session Tests ----


@pytest.mark.asyncio
async def test_local_chat_session_success_path(
    mock_chat_ui_class: MagicMock, mock_chat_ui_instance: AsyncMock
):
    """Tests the main success path of an interactive session for one turn."""
    setup_mock_chat_ui(
        mock_chat_ui_instance,
        messages=[UIUserMessage(content="Hello from user")],
        connected_states=[True, False]
    )

    mock_response = create_mock_response("Hello from user", "Hello from agent")
    mock_agent_call = AsyncMock(return_value=mock_response)

    with (
        patch.object(interactive, "ChatUI", mock_chat_ui_class),
        patch.object(interactive, "call", mock_agent_call),
    ):
        final_response = await interactive.local_chat(
            node=MockLLMNode,
            interactive_interface=mock_chat_ui_class,
            initial_message_to_user="Welcome!",
        )

    # Verify initialization
    mock_chat_ui_class.assert_called_once()
    mock_chat_ui_instance.connect.assert_awaited_once()

    # Verify messages sent
    mock_chat_ui_instance.send_message.assert_any_await(HILMessage(content="Welcome!"))
    mock_chat_ui_instance.send_message.assert_any_await(HILMessage(content="Hello from agent"))

    # Verify message received
    mock_chat_ui_instance.receive_message.assert_awaited_once()

    # Verify agent call
    mock_agent_call.assert_awaited_once()
    history_arg = mock_agent_call.call_args[0][1]
    assert history_arg[-1].content == "Hello from user"

    # Verify tools updated
    mock_chat_ui_instance.update_tools.assert_awaited_once()

    # Verify final response
    assert final_response is mock_response


@pytest.mark.asyncio
async def test_local_chat_loop_never_runs(
    mock_chat_ui_class: MagicMock, mock_chat_ui_instance: AsyncMock
):
    """Tests that the function returns None if the UI is never connected."""
    setup_mock_chat_ui(mock_chat_ui_instance, messages=[], connected_states=[False])
    mock_agent_call = AsyncMock()

    with (
        patch.object(interactive, "ChatUI", mock_chat_ui_class),
        patch.object(interactive, "call", mock_agent_call),
    ):
        final_response = await interactive.local_chat(
            node=MockLLMNode, 
            interactive_interface=mock_chat_ui_class
        )

    # Verify no interaction occurred
    assert final_response is None
    mock_chat_ui_instance.receive_message.assert_not_awaited()
    mock_agent_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_chat_terminates_on_turns(
    mock_chat_ui_class: MagicMock, mock_chat_ui_instance: AsyncMock
):
    """Tests that the session terminates after the specified number of turns."""
    connection_state = [True]

    async def mock_disconnect():
        connection_state[0] = False

    mock_chat_ui_instance.disconnect.side_effect = mock_disconnect
    type(mock_chat_ui_instance).is_connected = PropertyMock(
        side_effect=lambda: connection_state[0]
    )

    mock_chat_ui_instance.receive_message.return_value = UIUserMessage(content="Test")
    mock_response = LLMResponse(content="Response", message_history=MessageHistory())
    mock_agent_call = AsyncMock(return_value=mock_response)

    with (
        patch.object(interactive, "ChatUI", mock_chat_ui_class),
        patch.object(interactive, "call", mock_agent_call),
    ):
        await interactive.local_chat(
            node=MockLLMNode, 
            turns=1, 
            interactive_interface=mock_chat_ui_class
        )

    mock_chat_ui_instance.disconnect.assert_awaited_once()


# ---- Attachment Processing Tests ----


def test_process_attachment_with_file():
    """Test processing file attachments extracts data."""
    attachments = [
        UserMessageAttachment(type="file", data="base64data", name="file.txt")
    ]
    result = _process_attachment(attachments)
    assert result == ["base64data"]


def test_process_attachment_with_url():
    """Test processing URL attachments extracts URLs."""
    attachments = [
        UserMessageAttachment(type="url", url="https://example.com/image.png")
    ]
    result = _process_attachment(attachments)
    assert result == ["https://example.com/image.png"]


def test_process_attachment_with_mixed():
    """Test processing mixed file and URL attachments preserves order."""
    attachments = [
        UserMessageAttachment(type="file", data="base64data", name="file.txt"),
        UserMessageAttachment(type="url", url="https://example.com/image.png"),
        UserMessageAttachment(type="file", data="moredata", name="another.txt"),
    ]
    result = _process_attachment(attachments)
    assert result == ["base64data", "https://example.com/image.png", "moredata"]


def test_process_attachment_empty_list():
    """Test processing empty attachment list returns empty list."""
    result = _process_attachment([])
    assert result == []


# ---- Integration Tests with Attachments ----


@pytest.mark.asyncio
async def test_local_chat_with_url_attachments(
    mock_chat_ui_class: MagicMock, mock_chat_ui_instance: AsyncMock
):
    """Tests that URL attachments are correctly processed and added to message history."""
    url_attachment = UserMessageAttachment(
        type="url", 
        url="https://example.com/image.png"
    )
    
    setup_mock_chat_ui(
        mock_chat_ui_instance,
        messages=[UIUserMessage(content="Check this image", attachments=[url_attachment])],
        connected_states=[True, False]
    )

    mock_response = create_mock_response(
        "Check this image", 
        "I can see the image",
        attachments=["https://example.com/image.png"]
    )
    mock_agent_call = AsyncMock(return_value=mock_response)

    with (
        patch.object(interactive, "ChatUI", mock_chat_ui_class),
        patch.object(interactive, "call", mock_agent_call),
    ):
        await interactive.local_chat(
            node=MockLLMNode,
            interactive_interface=mock_chat_ui_class,
        )

    # Verify the attachment URL was added to the UserMessage
    mock_agent_call.assert_awaited_once()
    history_arg = mock_agent_call.call_args[0][1]
    assert history_arg[-1].content == "Check this image"
    assert len(history_arg[-1].attachment) == 1
    assert history_arg[-1].attachment[0].url == "https://example.com/image.png"


@pytest.mark.asyncio
async def test_local_chat_with_multiple_url_attachments(
    mock_chat_ui_class: MagicMock, mock_chat_ui_instance: AsyncMock
):
    """Tests that multiple URL attachments are correctly processed in order."""
    attachments = [
        UserMessageAttachment(type="url", url="https://example.com/image1.jpg"),
        UserMessageAttachment(type="url", url="https://example.com/image2.png")
    ]
    
    setup_mock_chat_ui(
        mock_chat_ui_instance,
        messages=[UIUserMessage(content="Multiple attachments", attachments=attachments)],
        connected_states=[True, False]
    )

    mock_response = create_mock_response(
        "Multiple attachments",
        "Got both attachments",
        attachments=["https://example.com/image1.jpg", "https://example.com/image2.png"]
    )
    mock_agent_call = AsyncMock(return_value=mock_response)

    with (
        patch.object(interactive, "ChatUI", mock_chat_ui_class),
        patch.object(interactive, "call", mock_agent_call),
    ):
        await interactive.local_chat(
            node=MockLLMNode,
            interactive_interface=mock_chat_ui_class,
        )

    # Verify both attachments were added in the correct order
    mock_agent_call.assert_awaited_once()
    history_arg = mock_agent_call.call_args[0][1]
    assert history_arg[-1].content == "Multiple attachments"
    assert len(history_arg[-1].attachment) == 2
    assert history_arg[-1].attachment[0].url == "https://example.com/image1.jpg"
    assert history_arg[-1].attachment[1].url == "https://example.com/image2.png"


@pytest.mark.asyncio
async def test_local_chat_with_no_attachments(
    mock_chat_ui_class: MagicMock, mock_chat_ui_instance: AsyncMock
):
    """Tests that messages without attachments have empty attachment list."""
    setup_mock_chat_ui(
        mock_chat_ui_instance,
        messages=[UIUserMessage(content="Just a text message")],
        connected_states=[True, False]
    )

    mock_response = create_mock_response("Just a text message", "Response")
    mock_agent_call = AsyncMock(return_value=mock_response)

    with (
        patch.object(interactive, "ChatUI", mock_chat_ui_class),
        patch.object(interactive, "call", mock_agent_call),
    ):
        await interactive.local_chat(
            node=MockLLMNode,
            interactive_interface=mock_chat_ui_class,
        )

    # Verify the message was processed with an empty attachment list
    mock_agent_call.assert_awaited_once()
    history_arg = mock_agent_call.call_args[0][1]
    assert history_arg[-1].content == "Just a text message"
    assert history_arg[-1].attachment == []