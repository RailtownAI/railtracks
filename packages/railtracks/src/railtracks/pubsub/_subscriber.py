import asyncio
from typing import Any, Callable, Coroutine, Union

from .messages import BroadcastEvent, RequestCompletionMessage


def event_subscriber(
    sub_callback: Callable[[Any], Union[None, Coroutine[None, None, None]]],
) -> Callable[[RequestCompletionMessage], Coroutine[None, None, None]]:
    """
    Wraps a user callback into a bus handler for broadcast events.

    Fires on each `BroadcastEvent` message (published by `rt.broadcast`), forwarding the
    event to `sub_callback`. This is the only traffic `BroadcastEvent` carries.
    """

    async def subscriber_handler(message: RequestCompletionMessage):
        if isinstance(message, BroadcastEvent):
            result = sub_callback(message.item)
            if asyncio.iscoroutine(result):
                await result

    return subscriber_handler
