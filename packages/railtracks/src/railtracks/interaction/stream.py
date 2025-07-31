from railtracks.context.central import get_parent_id, get_publisher
from railtracks.pubsub.messages import Streaming


async def broadcast(item: str):
    """
    Streams the given message

    This will trigger the broadcast_callback callback you have already provided.

    Args:
        item (str): The item you want to stream.
    """
    publisher = get_publisher()

    await publisher.publish(Streaming(node_id=get_parent_id(), streamed_object=item))
