import asyncio
from typing import Any, Callable, Coroutine, Union

from .messages import RequestCompletionMessage, Streaming


def stream_subscriber(
    sub_callback: Callable[[Any], Union[None, Coroutine[None, None, None]]],
) -> Callable[[RequestCompletionMessage], Coroutine[None, None, None]]:
    """
    Converts the basic streamer callback into a broadcast_callback handler designed to take in `RequestCompletionMessage`
    """

    async def subscriber_handler(item: RequestCompletionMessage):
        if isinstance(item, Streaming):
            result = sub_callback(item.streamed_object)
            if asyncio.iscoroutine(result):
                await result

    return subscriber_handler
