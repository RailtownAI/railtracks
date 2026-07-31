from __future__ import annotations

from railtracks.context.central import get_parent_id, get_publisher
from railtracks.pubsub.messages import Streaming


async def broadcast(item: str):
    """
    Broadcasts a one-off **event** to the session bus.

    This triggers the `broadcast_callback` you have provided to the `Session` (or via
    `rt.set_config`). Events are separate from LLM token streaming: token chunks flow directly
    to the `rt.astream` handle and never appear here.

    Args:
        item (str): The item you want to broadcast.
    """
    publisher = get_publisher()

    await publisher.publish(
        Streaming(node_id=get_parent_id(), streamed_object=item)
    )
