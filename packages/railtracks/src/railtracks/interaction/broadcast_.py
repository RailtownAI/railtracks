from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterable, Iterable, Union

from railtracks.context.central import get_parent_id, get_publisher, get_stream_id
from railtracks.pubsub.messages import Streaming

if TYPE_CHECKING:
    from railtracks.llm.response import Response


async def broadcast(item: str):
    """
    Broadcasts a one-off **event** to the session bus.

    This triggers the `broadcast_callback` you have already provided. Events are 
    separate from stream callbacks.

    Args:
        item (str): The item you want to broadcast.
    """
    publisher = get_publisher()

    await publisher.publish(
        Streaming(node_id=get_parent_id(), streamed_object=item, kind="event")
    )


async def broadcast_stream(
    stream: Union[AsyncIterable[Any], Iterable[Any]],
    channel: str = "default",
) -> Union[Response, str]:
    """
    Consumes a (sync or async) stream of chunks, broadcasting each `str` chunk on the bus,
    and returns the final result once the stream is exhausted.

    This is the bridge between a raw model stream and the railtracks streaming system: the
    framework uses it to forward a `model.astream_chat(...)` stream to the consumer of a
    streamed run (`rt.astream`) while still receiving the complete final response.

    If no consumer is attached to the run, the chunks are simply dropped and this behaves
    like a buffered call — so the same node works with and without streaming.

    Behavior:
    - Every `str` item is published on `channel` as **stream** traffic (consumed by
      `rt.astream`; not delivered to a `broadcast_callback`, which is for one-off
      `rt.broadcast` events) and accumulated.
    - The first non-`str` item is treated as the stream's final result (model streams such as
      `astream_chat` yield a final `Response` after the chunks).

    Args:
        stream: An async iterable (e.g. `model.astream_chat(...)`) or sync iterable yielding
            `str` chunks, optionally terminated by a final non-`str` result.
        channel: The named channel to emit chunks on. Defaults to `"default"`.

    Returns:
        The final non-`str` item yielded by the stream (a `Response` for model streams), or the
        concatenation of all `str` chunks if the stream never yielded a final item.
    """
    final: Any = None
    parts: list[str] = []
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
                parts.append(item)
                await _publish_chunk(item)
            else:
                final = item
    else:
        for item in stream:  # type: ignore[union-attr]
            if isinstance(item, str):
                parts.append(item)
                await _publish_chunk(item)
            else:
                final = item

    if final is not None:
        return final

    return "".join(parts)
