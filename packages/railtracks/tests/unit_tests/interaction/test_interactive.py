import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from railtracks import interactive

from railtracks.built_nodes.concrete._llm_base import LLMBase
from railtracks.built_nodes.concrete.response import LLMResponse
from railtracks.human_in_the_loop import ChatUI, HIL, HILMessage
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import UserMessage, AssistantMessage
from railtracks.nodes.nodes import Node


class MockLLMNode(LLMBase):
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


# --- Test Cases ---


@pytest.mark.asyncio
async def test_interactive_with_invalid_node():
    """Verifies `interactive.local_chat` raises ValueError for non-LLMBase nodes."""

    class InvalidNode(Node):
        pass

    with pytest.raises(
        ValueError,
        match="Interactive sessions only support nodes that are children of LLMBase.",
    ):
        await interactive.local_chat(node=InvalidNode)


@pytest.mark.asyncio
async def test_local_chat_session_success_path(
    mock_chat_ui_class: MagicMock, mock_chat_ui_instance: AsyncMock
):
    """Tests the main success path of an interactive session for one turn."""
    is_connected_mock = PropertyMock(side_effect=[True, False])
    type(mock_chat_ui_instance).is_connected = is_connected_mock

    mock_chat_ui_instance.receive_message.return_value = HILMessage(
        content="Hello from user"
    )

    mock_response = LLMResponse(
        content="Hello from agent",
        message_history=MessageHistory(
            [UserMessage("Hello from user"), AssistantMessage("Hello from agent")]
        ),
    )
    mock_agent_call = AsyncMock(return_value=mock_response)

    with (
        patch.object(interactive, "ChatUI", mock_chat_ui_class),
        patch.object(interactive, "call", mock_agent_call),
    ):
        final_response = await interactive.local_chat(
            node=MockLLMNode,
            interactive_interface=mock_chat_ui_class,  # Pass the mock class here
            initial_message_to_user="Welcome!",
        )

    mock_chat_ui_class.assert_called_once()
    mock_chat_ui_instance.connect.assert_awaited_once()

    mock_chat_ui_instance.send_message.assert_any_await(HILMessage(content="Welcome!"))
    mock_chat_ui_instance.send_message.assert_any_await(
        HILMessage(content="Hello from agent")
    )

    mock_chat_ui_instance.receive_message.assert_awaited_once()

    mock_agent_call.assert_awaited_once()
    history_arg = mock_agent_call.call_args[0][1]
    assert history_arg[-1].content == "Hello from user"

    mock_chat_ui_instance.update_tools.assert_awaited_once()

    assert final_response is mock_response


@pytest.mark.asyncio
async def test_local_chat_loop_never_runs(
    mock_chat_ui_class: MagicMock, mock_chat_ui_instance: AsyncMock
):
    """Tests that the function returns None if the UI is never connected."""
    is_connected_mock = PropertyMock(return_value=False)
    type(mock_chat_ui_instance).is_connected = is_connected_mock
    mock_agent_call = AsyncMock()

    with (
        patch.object(interactive, "ChatUI", mock_chat_ui_class),
        patch.object(interactive, "call", mock_agent_call),
    ):
        final_response = await interactive.local_chat(
            node=MockLLMNode, interactive_interface=mock_chat_ui_class
        )

    # ASSERT
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

    mock_chat_ui_instance.receive_message.return_value = HILMessage(content="Test")
    mock_response = LLMResponse(content="Res", message_history=MessageHistory())
    mock_agent_call = AsyncMock(return_value=mock_response)

    with (
        patch.object(interactive, "ChatUI", mock_chat_ui_class),
        patch.object(interactive, "call", mock_agent_call),
    ):
        await interactive.local_chat(
            node=MockLLMNode, turns=1, interactive_interface=mock_chat_ui_class
        )

    mock_chat_ui_instance.disconnect.assert_awaited_once()
