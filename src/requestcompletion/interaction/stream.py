from ..context.central import get_parent_id, get_publisher
from ..pubsub.messages import Streaming


async def stream(item: str):
    """
    Streams the given message

    This will trigger the subscriber callback you have already provided.

    Args:
        item (str): The item you want to stream.
    """
    publisher = get_publisher()

    await publisher.publish(Streaming(node_id=get_parent_id(), streamed_object=item))
