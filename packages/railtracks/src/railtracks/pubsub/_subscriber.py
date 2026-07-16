import asyncio
from typing import Any, Callable, Coroutine, Mapping, Union

from .messages import RequestCompletionMessage, Streaming


def stream_chunk_subscriber(
    callback: Union[
        Callable[[Any], Any],
        Mapping[str, Callable[[Any], Any]],
    ],
) -> Callable[[RequestCompletionMessage], Coroutine[None, None, None]]:
    """
    Converts a `stream_callback` (a single callable, or a mapping of channel name -> callable)
    into a subscriber handler for `Streaming` messages.

    - A single callable receives every streamed/broadcast item regardless of channel.
    - A mapping routes each item to the callable registered under the item's channel name;
      items on channels without a registered callable are dropped silently.

    Callables may be sync or async.
    """

    async def subscriber_handler(item: RequestCompletionMessage):
        if not isinstance(item, Streaming):
            return

        if isinstance(callback, Mapping):
            fn = callback.get(item.channel)
            if fn is None:
                return
        else:
            fn = callback

        result = fn(item.streamed_object)
        if asyncio.iscoroutine(result):
            await result

    return subscriber_handler
