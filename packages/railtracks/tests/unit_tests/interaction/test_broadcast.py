import pytest
from unittest.mock import AsyncMock, patch
from railtracks.interaction.broadcast_ import broadcast
from railtracks.pubsub.messages import BroadcastEvent


@pytest.mark.asyncio
async def test_broadcast_publishes_event_message():
    with patch("railtracks.interaction.broadcast_.get_publisher") as mock_get_publisher, \
         patch("railtracks.interaction.broadcast_.get_parent_id") as mock_get_parent_id:

        # Setup mocks
        mock_publisher = AsyncMock()
        mock_get_publisher.return_value = mock_publisher
        mock_get_parent_id.return_value = "mock_node_id"

        # Call the function
        await broadcast("test_message")

        mock_publisher.publish.assert_awaited_once()

        # Extract the actual BroadcastEvent object
        message = mock_publisher.publish.await_args.args[0]
        assert isinstance(message, BroadcastEvent)
        assert message.node_id == "mock_node_id"
        assert message.item == "test_message"
