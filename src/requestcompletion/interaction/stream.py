from ..context.central import get_publisher, get_parent_id
from ..pubsub.messages import Streaming


async def stream(item: str):
    """
    Streams the given message

    It will trigger the callback provided in the runner_config.

    Args:
        item (str): The item you want to stream.
    """
    publisher = get_publisher()

    await publisher.publish(Streaming(node_id=get_parent_id(), streamed_object=item))
