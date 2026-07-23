from __future__ import annotations

from typing import Any, AsyncIterable, Iterable, Union

from railtracks.context.central import get_parent_id, get_publisher, get_stream_id
from railtracks.exceptions.errors import LLMError
from railtracks.llm.response import Response
from railtracks.pubsub.messages import Streaming


async def broadcast(item: str, channel: str = "default"):
    """
    Broadcasts a one-off **event** to the session bus.

    The event is delivered to a `broadcast_callback` and, when emitted inside a streamed run,
    to `rt.astream` (which can filter to a single channel with `on_channel`). Events travel on
    a separate lane from stream chunks, so a `broadcast_callback` never receives tokens.

    Args:
        item (str): The item you want to broadcast.
        channel (str): The named channel to emit on. Consumers can select a single channel
            (e.g. `stream.on_channel("status")`). Defaults to `"default"`.
    """
    publisher = get_publisher()

    await publisher.publish(
        Streaming(
            node_id=get_parent_id(),
            streamed_object=item,
            channel=channel,
            stream_id=get_stream_id(),
            kind="event",
        )
    )


async def broadcast_stream(
    stream: Union[AsyncIterable[Any], Iterable[Any]],
    channel: str = "default",
) -> Response:
    """
    Forwards a model's token stream to the run's streaming consumers and returns its complete
    `Response`.

    Each `str` chunk is published on `channel` as stream traffic (`rt.astream` receives it;
    one-off `rt.broadcast` events go to `broadcast_callback`, not here). The stream's final
    non-`str` item is the complete `Response`, which is returned. When no consumer is attached
    the chunks are simply dropped, so the same node works with or without streaming.

    Like the buffered model call, this fails fast: if the stream ends without producing a
    `Response`, an `LLMError` is raised rather than returning a partial result.

    Args:
        stream: An async or sync iterable (e.g. `model.astream_chat(...)`) yielding `str`
            chunks terminated by a final `Response`.
        channel: The named channel to emit chunks on. Defaults to `"default"`.

    Returns:
        Response: The complete response yielded at the end of the stream.

    Raises:
        LLMError: If the stream is exhausted without yielding a final `Response`.
    """
    final: Any = None
    publisher = get_publisher()

    async def _publish_chunk(chunk: str) -> None:
        await publisher.publish(
            Streaming(
                node_id=get_parent_id(),
                streamed_object=chunk,
                channel=channel,
                stream_id=get_stream_id(),
                kind="stream",
            )
        )

    if hasattr(stream, "__aiter__"):
        async for item in stream:  # type: ignore[union-attr]
            if isinstance(item, str):
                await _publish_chunk(item)
            else:
                final = item
    else:
        for item in stream:  # type: ignore[union-attr]
            if isinstance(item, str):
                await _publish_chunk(item)
            else:
                final = item

    if not isinstance(final, Response):
        raise LLMError(reason="The stream did not yield a final Response object.")

    return final
