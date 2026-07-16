from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterable, Iterable, Union, overload
from uuid import uuid4

from railtracks.context.central import get_parent_id, get_publisher, get_stream_id
from railtracks.pubsub.messages import StreamEnd, Streaming, StreamingKind

if TYPE_CHECKING:
    from railtracks.llm.response import Response


async def _publish_item(item: Any, channel: str, kind: StreamingKind) -> None:
    """Publishes one item on the broadcast bus, tagged with its traffic kind.

    The kind separates the two callback lanes: `"event"` items go to `broadcast_callback`,
    `"stream"` chunks go to `stream_callback`. Scoped consumers (`rt.astream`,
    `rt.context.get_stream`) receive both kinds and separate traffic by channel instead.
    """
    publisher = get_publisher()

    await publisher.publish(
        Streaming(
            node_id=get_parent_id(),
            streamed_object=item,
            channel=channel,
            stream_id=get_stream_id(),
            kind=kind,
        )
    )


async def broadcast(item: Any, channel: str = "default"):
    """
    Broadcasts a one-off **event** to the session's broadcast bus.

    Consumers attached to the run will receive it:

    - A configured `broadcast_callback` (passive event listener) is invoked with the item;
      when the callback is a dict, the item is routed to the callable registered under
      `channel` (a single callable receives every event on every channel). Events do NOT
      reach `stream_callback` — that lane carries `rt.broadcast_stream` chunks only.
    - `rt.astream(...)` / `Stream.route(...)` yield/route it (scoped consumers see both
      events and stream chunks; use channels to separate them).
    - `rt.context.get_stream(channel, ...)` (pull mode, from inside the run) yields it.

    If nothing is listening, the item is simply dropped — broadcasting is always safe.

    For a *continuous* production (an LLM token stream, a chunked file read), use
    `rt.broadcast_stream` instead: its chunks are tagged as stream traffic and it publishes
    a completion marker consumers can count.

    Args:
        item: The item you want to broadcast.
        channel: The named channel to emit on. Defaults to `"default"`.
    """
    await _publish_item(item, channel, "event")


@overload
async def broadcast_stream(
    stream: Union[AsyncIterable[str], Iterable[str]],
    channel: str = "default",
) -> str:
    """A stream of plain `str` chunks (no terminal item) resolves to the accumulated text."""


@overload
async def broadcast_stream(
    stream: Union[AsyncIterable[Union[str, Response]], Iterable[Union[str, Response]]],
    channel: str = "default",
) -> Response:
    """A model stream (`str` chunks followed by a final `Response`) resolves to that `Response`."""


async def broadcast_stream(
    stream: Union[AsyncIterable[Any], Iterable[Any]],
    channel: str = "default",
) -> Union[Response, str]:
    """
    Consumes a (sync or async) stream of chunks, broadcasting each `str` chunk on the given
    channel, and returns the final result once the stream is exhausted.

    This is the bridge between a raw model stream and the railtracks streaming system: inside a
    custom node you can forward a `model.astream_chat(...)` stream to whoever is consuming the
    run (`rt.astream`, `Stream.route()`, or a `stream_callback`) while still receiving the
    complete final response to build your node's return value:

    ```python
    @rt.function_node
    async def poem(topic: str) -> str:
        model = rt.llm.OpenAILLM("gpt-4o-mini")
        response = await rt.broadcast_stream(
            model.astream_chat([UserMessage(f"Write a poem about {topic}.")])
        )
        return response.message.content
    ```

    If no consumer is attached to the run, the chunks are simply dropped and this behaves like
    a buffered call — so the same node works with and without streaming.

    Behavior:
    - Every `str` item is published on `channel` as **stream** traffic (it reaches
      `stream_callback`, not `broadcast_callback` — use `rt.broadcast` for one-off events)
      and accumulated.
    - The first non-`str` item is treated as the stream's final result (model streams such as
      `astream_chat` yield a final `Response` after the chunks).
    - When the stream is exhausted — or the producer raises — a `StreamEnd` marker is
      published on the channel (after all chunks; dispatch is FIFO). Channel consumers
      (`rt.context.get_stream`) use these markers to know when a production has finished.

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

    try:
        if hasattr(stream, "__aiter__"):
            async for item in stream:  # type: ignore[union-attr]
                if isinstance(item, str):
                    parts.append(item)
                    await _publish_item(item, channel, "stream")
                else:
                    final = item
        else:
            for item in stream:  # type: ignore[union-attr]
                if isinstance(item, str):
                    parts.append(item)
                    await _publish_item(item, channel, "stream")
                else:
                    final = item
    finally:
        # always mark this production as finished — even when the producer raised — so
        # channel consumers counting productions are released rather than left hanging.
        await publisher.publish(
            StreamEnd(
                channel=channel,
                node_id=get_parent_id(),
                stream_id=get_stream_id(),
                source_id=str(uuid4()),
            )
        )

    if final is not None:
        return final

    return "".join(parts)
