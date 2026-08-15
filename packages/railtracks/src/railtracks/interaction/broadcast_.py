from __future__ import annotations

from railtracks.context.central import get_parent_id, get_publisher
from railtracks.pubsub.messages import BroadcastEvent


async def broadcast(item: str):
    """
    Broadcasts a one-off **event** to the session bus.

    This triggers the `broadcast_callback` you have provided to the `Session` (or via
    `rt.set_config`). Each broadcast is a discrete event, independent of any LLM token
    output an agent produces.

    Args:
        item (str): The item you want to broadcast.
    """
    publisher = get_publisher()

    await publisher.publish(BroadcastEvent(node_id=get_parent_id(), item=item))
