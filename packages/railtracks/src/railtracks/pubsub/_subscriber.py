import asyncio
from typing import Any, Callable, Coroutine, Union

from .messages import RequestCompletionMessage, Streaming, StreamingKind


def stream_subscriber(
    sub_callback: Callable[[Any], Union[None, Coroutine[None, None, None]]],
    kind: StreamingKind = "event",
) -> Callable[[RequestCompletionMessage], Coroutine[None, None, None]]:
    """
    Wraps a user callback into a bus handler that receives one traffic lane.

    The two lanes are kept separate so consumers never mix them up:
    - `kind="event"` (default): one-off `rt.broadcast` items — this drives `broadcast_callback`.
    - `kind="stream"`: chunks from `rt.broadcast_stream` / LLM token streaming — this drives
      `stream_callback`.

    A handler only fires on `Streaming` messages matching its `kind`, so a `broadcast_callback`
    is never flooded with tokens when a run streams, and a `stream_callback` never sees one-off
    broadcast events.
    """

    async def subscriber_handler(item: RequestCompletionMessage):
        if isinstance(item, Streaming) and item.kind == kind:
            result = sub_callback(item.streamed_object)
            if asyncio.iscoroutine(result):
                await result

    return subscriber_handler
