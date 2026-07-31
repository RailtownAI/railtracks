import asyncio
from typing import Any, Callable, Coroutine, Union

from .messages import RequestCompletionMessage, Streaming


def event_subscriber(
    sub_callback: Callable[[Any], Union[None, Coroutine[None, None, None]]],
) -> Callable[[RequestCompletionMessage], Coroutine[None, None, None]]:
    """
    Wraps a user callback into a bus handler for one-off broadcast events.

    The handler fires only on `Streaming` messages (published by `rt.broadcast`), forwarding
    the broadcast item to `sub_callback`. LLM token streaming does not flow through the bus —
    it is consumed directly by the `rt.astream` handle — so this callback only ever sees
    explicit `rt.broadcast` events.
    """

    async def subscriber_handler(item: RequestCompletionMessage):
        if isinstance(item, Streaming):
            result = sub_callback(item.streamed_object)
            if asyncio.iscoroutine(result):
                await result

    return subscriber_handler
