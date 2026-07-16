from __future__ import annotations

import asyncio
import time
import warnings
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Generator,
    Generic,
    Mapping,
    NoReturn,
    ParamSpec,
    TypeVar,
    overload,
)
from uuid import uuid4

from railtracks.context.central import (
    activate_publisher,
    get_local_config,
    get_parent_id,
    get_publisher,
    get_run_id,
    get_stream_id,
    is_context_present,
)
from railtracks.exceptions import GlobalTimeOutError
from railtracks.nodes.utils import extract_node_from_function
from railtracks.pubsub.messages import (
    FatalFailure,
    RequestCompletionMessage,
    RequestCreation,
    RequestFinishedBase,
    StreamEnd,
    Streaming,
)
from railtracks.pubsub.utils import output_mapping
from railtracks.utils.config import BroadcastCallback
from railtracks.utils.logging import get_rt_logger

if TYPE_CHECKING:
    from railtracks._session import Session
    from railtracks.built_nodes.concrete import RTFunction
    from railtracks.nodes.nodes import Node

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")

logger = get_rt_logger(__name__)

# sentinel used to mark "no result yet" (None is a valid node result)
_UNSET = object()

# queue-item tags used between get_stream's subscriber and its consuming generator
_CHUNK = "chunk"
_END = "end"


class _Terminated:
    """Sentinel type returned by `_next_channel_item` once `until` fired and the buffer drained."""


_TERMINATED = _Terminated()


async def _drain_channel(
    queue: asyncio.Queue[tuple[str, Any]],
    streams: int | None,
    until: asyncio.Future[Any] | None,
    unsubscribe: Callable[[], None],
) -> AsyncIterator[Any]:
    """Yields queued channel chunks until enough `StreamEnd` markers (or `until`) arrive.

    This is the (lazy) generator half of `get_stream`; the eager half — subscribing to the
    bus — must run at `get_stream()` call time, before the first iteration, which is why the
    two are separate functions (an async generator body does not execute until first
    `__anext__`, and chunks emitted before then would otherwise be lost).

    Termination is fully event-driven — no polling:
    - end-markers ride the same FIFO queue as the chunks, so when the `streams`-th marker is
      dequeued every chunk of those productions has already been yielded;
    - while idle we race `queue.get()` against the optional `until` future and wake on
      whichever fires first.

    Always unsubscribes (via `unsubscribe`) when iteration ends — on normal completion,
    an early `break` (the async generator's `aclose`), or garbage collection.
    """
    ends_seen = 0
    try:
        while True:
            item = await _next_channel_item(queue, until)
            if isinstance(item, _Terminated):
                return
            if item is None:
                continue  # `until` fired mid-wait; loop drains stragglers, then terminates
            kind, payload = item
            if kind == _CHUNK:
                yield payload
            else:  # _END: one production on this channel finished
                ends_seen += 1
                if streams is not None and ends_seen >= streams:
                    return
    finally:
        unsubscribe()


async def _next_channel_item(
    queue: asyncio.Queue[tuple[str, Any]],
    until: asyncio.Future[Any] | None,
) -> tuple[str, Any] | _Terminated | None:
    """Gets the next queued item, racing against `until` when one is provided.

    Returns the item, `_TERMINATED` when `until` is done and the queue is drained, or None
    when `until` fired while waiting (caller loops to drain any stragglers).
    """
    try:
        return queue.get_nowait()
    except asyncio.QueueEmpty:
        pass

    if until is None:
        return await queue.get()

    # queue is empty; if the terminator already fired no more chunks can arrive
    # (bus dispatch is FIFO: everything published before it was already delivered)
    if until.done():
        return _TERMINATED

    # race: the next item vs. the terminator, whichever happens first
    getter = asyncio.ensure_future(queue.get())
    try:
        await asyncio.wait({getter, until}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        if not getter.done():
            # cancelling a Queue.get never loses items: items only leave the
            # queue via get_nowait/get returning, and we re-drain on loop entry.
            getter.cancel()

    if getter.done() and not getter.cancelled():
        return getter.result()
    return None


def get_stream(
    channel: str = "default",
    *,
    streams: int | None = 1,
    until: asyncio.Future[Any] | None = None,
) -> AsyncIterator[Any]:
    """
    Consume a broadcast channel *from inside a run*, as its chunks arrive.

    This is the intra-run counterpart to `rt.astream`: rather than launching and consuming a
    top-level call, it taps a channel that some *other, concurrently running* part of the same
    run is broadcasting to (via `rt.broadcast` / `rt.broadcast_stream`). The typical shape is a
    producer node launched as a task while the current frame folds its stream in:

    ```python
    @rt.function_node
    async def orchestrator(topic: str) -> str:
        task = asyncio.create_task(rt.call(producer, topic=topic))  # streams on "tokens"
        async for chunk in rt.context.get_stream("tokens"):          # ends with the stream
            print(chunk, end="", flush=True)                         # live child tokens
        return (await task).text
    ```

    Termination — by counting finished productions:
        Every `rt.broadcast_stream` publishes a `StreamEnd` marker on its channel when it
        finishes (even if the producer raised). By default (`streams=1`) iteration ends once
        **one** production has completed — so for the common single-producer fold the loop
        above just ends by itself, no extra signal needed.

        - Several producers on one channel? `streams=N` ends after N productions.
        - Open-ended feed (unknown producers, or bare `rt.broadcast` items, which carry no
          markers)? `streams=None` and bound the loop yourself: `break`, or pass
          `until=some_task` to stop when that task completes (also useful as a safety net —
          e.g. `until=task` guards against a producer that crashes before ever reaching its
          `broadcast_stream` call, in which case no marker is ever published).

        Whichever of `streams` / `until` is satisfied first ends the iteration; buffered
        chunks are always drained before stopping.

    Scope: only chunks belonging to the current stream scope are delivered (child frames
    inherit the scope, so a producer started with `rt.call` from here is included; unrelated
    concurrent runs are not). In a plain non-streamed run the scope id is None, so give
    concurrent independent folds distinct channel names.

    Subscription happens eagerly when this function is called — before the first iteration —
    so chunks emitted between launching the producer and starting to iterate are not missed.

    Args:
        channel: The channel name to consume. Defaults to `"default"`.
        streams: How many finished productions (`StreamEnd` markers) end the iteration.
            Defaults to 1 — one `broadcast_stream` production. Pass None for an unbounded
            feed that you terminate yourself (`break` or `until`).
        until: Optional future/task that also ends the iteration when done (after draining).

    Returns:
        AsyncIterator[Any]: An async iterator over the chunks broadcast on `channel` within
            the current run.
    """
    stream_id = get_stream_id()
    publisher = get_publisher()
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

    def _subscriber(message: RequestCompletionMessage) -> None:
        if isinstance(message, Streaming):
            if message.stream_id == stream_id and message.channel == channel:
                queue.put_nowait((_CHUNK, message.streamed_object))
        elif isinstance(message, StreamEnd):
            if message.stream_id == stream_id and message.channel == channel:
                queue.put_nowait((_END, None))

    # subscribe eagerly (synchronously) so nothing emitted before the first iteration is lost
    sub_id = publisher.subscribe(_subscriber, name="channel stream subscriber")

    def _unsubscribe() -> None:
        try:
            publisher.unsubscribe(sub_id)
        except Exception:
            logger.debug("Failed to unsubscribe channel stream.", exc_info=True)

    return _drain_channel(queue, streams, until, _unsubscribe)


class Stream(Generic[_TOutput], AsyncIterator[Any]):
    """
    The handle returned by `rt.astream(...)` (and `Flow.astream(...)`).

    A `Stream` is an async iterator over the chunks emitted during a streamed invocation. It
    yields *only* chunks (typically `str` tokens); the node's final return value is exposed
    separately so there is never any ambiguity between a chunk and the final result:

    ```python
    stream = rt.astream(agent, user_input="Write a poem.")
    async for chunk in stream:
        print(chunk, end="", flush=True)
    final = stream.result  # the node's complete return value (e.g. StringResponse)
    ```

    The final result may legitimately differ from the concatenation of the streamed chunks —
    for example when output guardrails gate/correct the buffered response after the raw tokens
    were streamed.

    A `Stream` is also awaitable: `final = await stream` consumes the stream to completion
    (discarding any unread chunks) and returns the final result. This is handy when you stop
    iterating early (`break`) but still want the run to finish and the result to be available —
    the underlying invocation always runs to completion; breaking out of the loop does not
    cancel it.

    To consume only a specific named channel, chain `on_channel` before iterating:

    ```python
    async for chunk in rt.astream(node, topic="x").on_channel("final"):
        ...
    ```

    For push-style consumption, `route` dispatches chunks to handlers by channel and returns
    the final result:

    ```python
    final = await rt.astream(node, topic="x").route({"draft": fn1, "final": fn2})
    ```

    Error behavior: if the invoked node raises, the exception propagates out of the `async for`
    loop (or the `await`), exactly like `rt.call`.

    Notes:
        - Iterate (and await) a `Stream` from a single task.
        - The stream honors the session's `timeout` as a wall-clock limit on the whole run.
    """

    def __init__(
        self,
        node: type[Node[_P, _TOutput]],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        channel: str | None = None,
        owned_session: Session | None = None,
    ):
        """
        Creates a new (not yet started) streamed invocation. Prefer `rt.astream(...)` /
        `Flow.astream(...)` over constructing this directly.

        Args:
            node: The node type to invoke.
            args: The positional arguments to pass to the node.
            kwargs: The keyword arguments to pass to the node.
            channel: Only yield chunks emitted on this named channel (None = all channels).
            owned_session: A session this stream is responsible for closing once the run
                completes (used by `Flow.astream`; `rt.astream` creates one lazily when
                called outside any session).
        """
        self._node = node
        self._args = args
        self._kwargs = kwargs
        # None means "receive chunks from every channel"; a name filters to that channel only.
        self._channel = channel

        # the request id doubles as the stream scope id used to tag every chunk of this run
        self._request_id = str(uuid4())

        self._queue: asyncio.Queue[tuple[str, Any]] | None = None
        self._started = False
        self._finished = False
        self._result: Any = _UNSET
        self._error: BaseException | None = None
        self._sub_id: str | None = None
        self._deadline: float | None = None
        self._timeout: float | None = None
        # a session this stream is responsible for closing once the run completes
        self._owned_session: Session | None = owned_session

    # ------------------------------------------------------------------ configuration

    def on_channel(self, channel: str | None) -> Stream[_TOutput]:
        """
        Restricts this stream to chunks emitted on the given named channel.

        Must be called before iteration starts. Returns `self` so it can be chained:

        ```python
        async for chunk in rt.astream(node, topic="x").on_channel("final"):
            ...
        ```

        Why a method rather than a `channel=` argument on `astream`: `astream` forwards its
        `*args`/`**kwargs` straight to the target node (like `rt.call`), so a `channel=`
        keyword would collide with any node that declares its own `channel` parameter, and is
        in any case disallowed by the type system after a forwarded `*args`. Selecting the
        channel on the returned handle keeps the node's own arguments unambiguous.

        Args:
            channel: The channel name to filter on, or None to receive every channel
                (the default behavior).

        Returns:
            Stream[_TOutput]: This stream, for chaining.

        Raises:
            RuntimeError: If the stream has already started iterating.
        """
        if self._started:
            raise RuntimeError(
                "on_channel() must be called before the stream is iterated."
            )
        self._channel = channel
        return self

    # ------------------------------------------------------------------ lifecycle

    async def _start(self) -> None:
        """Lazily starts the run on first iteration: subscribes to the bus, then publishes
        the entry request with streaming enabled."""
        if self._started:
            return
        self._started = True

        if not is_context_present():
            # lazy import to prevent a circular import (same pattern as rt.call)
            from railtracks import Session

            self._owned_session = Session()

        await activate_publisher()
        publisher = get_publisher()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        self._queue = queue

        request_id = self._request_id

        def _subscriber(message: RequestCompletionMessage) -> None:
            if isinstance(message, Streaming):
                if message.stream_id != request_id:
                    return
                if self._channel is not None and message.channel != self._channel:
                    return
                # keep the channel alongside the payload so route() can dispatch by it
                queue.put_nowait(("chunk", (message.channel, message.streamed_object)))
            elif isinstance(message, RequestFinishedBase):
                if message.request_id == request_id:
                    queue.put_nowait(("done", message))
            elif isinstance(message, FatalFailure):
                queue.put_nowait(("done", message))

        # subscribe BEFORE publishing the request so no chunk can be missed
        self._sub_id = publisher.subscribe(_subscriber, name="astream subscriber")

        self._timeout = get_local_config().timeout
        self._deadline = (
            None if self._timeout is None else time.monotonic() + self._timeout
        )

        await publisher.publish(
            RequestCreation(
                current_node_id=get_parent_id(),
                current_run_id=get_run_id(),
                new_request_id=request_id,
                running_mode="async",
                new_node_type=self._node,
                args=self._args,
                kwargs=self._kwargs,
                stream=True,
            )
        )

    def _cleanup(self) -> None:
        """Unsubscribes from the bus and closes the owned session (if any)."""
        if self._sub_id is not None:
            try:
                get_publisher().unsubscribe(self._sub_id)
            except Exception:
                # the publisher may already be gone (e.g. session shut down); nothing to do.
                logger.debug("Failed to unsubscribe astream subscriber.", exc_info=True)
            self._sub_id = None

        if self._owned_session is not None:
            session = self._owned_session
            self._owned_session = None
            session.__exit__(None, None, None)

    # ------------------------------------------------------------------ iteration

    def __aiter__(self) -> Stream[_TOutput]:
        return self

    async def __anext__(self) -> Any:
        _, chunk = await self._next_tagged()
        return chunk

    async def _next_tagged(self) -> tuple[str, Any]:
        """Core iteration step: returns the next `(channel, chunk)` pair.

        Raises `StopAsyncIteration` once the run finishes (resolving `.result`), or the
        node's error / `GlobalTimeOutError` like `__anext__` does. `route()` uses the channel;
        `__anext__` discards it (public iteration yields chunks only).
        """
        if self._finished:
            raise StopAsyncIteration

        await self._start()
        assert self._queue is not None

        remaining: float | None = None
        if self._deadline is not None:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                self._finish_with_timeout()

        try:
            kind, payload = await asyncio.wait_for(self._queue.get(), timeout=remaining)
        except asyncio.TimeoutError:
            self._finish_with_timeout()

        if kind == "chunk":
            return payload  # (channel, chunk)

        # the run has finished: resolve the final result (or raise the node's error)
        self._finished = True
        self._cleanup()
        try:
            self._result = output_mapping(payload)
        except BaseException as e:
            self._error = e
            raise
        raise StopAsyncIteration

    async def route(self, handlers: BroadcastCallback) -> _TOutput:
        """
        Consumes this stream push-style, dispatching each chunk to handler(s) by channel, and
        returns the node's final result.

        This is the per-call push consumer: unlike a session-level `stream_callback`
        (which passively observes streamed chunks from *every* run in the session), `route`
        receives only this stream's own chunks and is what actually enables the streaming.

        ```python
        final = await flow.astream("Write a poem.").route(
            {"draft": to_editor_pane, "final": to_chat_pane}
        )
        ```

        Args:
            handlers: A single callable (receives every chunk of this stream), or a mapping of
                channel name -> callable (chunks on unregistered channels are skipped).
                Callables may be sync or async.

        Returns:
            _TOutput: The node's final return value (same as `stream.result`).

        Raises:
            BaseException: The node's own exception, if the run failed.

        Note:
            Only chunks in *this* stream's scope are routed. A nested `rt.astream` inside the
            invoked node creates its own scope — consume those with a session-level
            `stream_callback` instead. If some registered channels never receive a chunk, a
            `UserWarning` is emitted when the stream ends.
        """
        registered = set(handlers.keys()) if isinstance(handlers, Mapping) else None
        fired: set[str] = set()
        seen: set[str] = set()

        while True:
            try:
                channel, chunk = await self._next_tagged()
            except StopAsyncIteration:
                break

            seen.add(channel)
            if isinstance(handlers, Mapping):
                fn = handlers.get(channel)
                if fn is None:
                    continue
                fired.add(channel)
            else:
                fn = handlers

            result = fn(chunk)
            if asyncio.iscoroutine(result):
                await result

        if registered is not None:
            unused = registered - fired
            if unused:
                detail = (
                    f"; observed channels were {sorted(seen)}"
                    if seen
                    else " — the stream produced no chunks"
                )
                # a UserWarning (not a log record) so it is visible by default
                warnings.warn(
                    f"route(): handler channels {sorted(unused)} never received any "
                    f"chunks{detail}.",
                    UserWarning,
                    stacklevel=2,
                )

        return self.result

    def _finish_with_timeout(self) -> NoReturn:
        """Marks the stream as finished and raises the global timeout error."""
        assert self._timeout is not None, "timeout can only fire when one is configured"
        error = GlobalTimeOutError(timeout=self._timeout)
        self._finished = True
        self._error = error
        self._cleanup()
        raise error

    # ------------------------------------------------------------------ result access

    @property
    def result(self) -> _TOutput:
        """
        The node's final return value.

        Only available once the stream has been fully consumed (or awaited).

        Returns:
            _TOutput: The value the node returned (e.g. a `StringResponse` for agents).

        Raises:
            RuntimeError: If the stream has not finished yet.
            BaseException: The node's own exception, if the run failed.
        """
        if self._error is not None:
            raise self._error
        if self._result is _UNSET:
            raise RuntimeError(
                "The stream has not finished yet. Iterate it to completion (or use "
                "`final = await stream`) before accessing `.result`."
            )
        return self._result

    async def _drain(self) -> _TOutput:
        """Consumes the rest of the stream (discarding unread chunks) and returns the result."""
        async for _ in self:
            pass
        return self.result

    def __await__(self) -> Generator[Any, None, _TOutput]:
        """Awaiting a Stream consumes it to completion and returns the final result."""
        return self._drain().__await__()


@overload
def astream(
    node_: type[Node[_P, _TOutput]],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> Stream[_TOutput]: ...


@overload
def astream(
    node_: RTFunction[_P, _TOutput],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> Stream[_TOutput]: ...


def astream(
    node_: type[Node[_P, _TOutput]] | RTFunction[_P, _TOutput],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> Stream[_TOutput]:
    """
    Invoke a node with streaming enabled and return a `Stream` over its emitted chunks.

    This is the pull-based streaming entry point of railtracks. The same node/agent object
    serves streaming and non-streaming runs — `rt.call` runs it buffered, `rt.astream` streams
    it. Streaming is frame-local: only the node you invoke here streams its LLM responses;
    nested `rt.call` children run buffered (their explicit `rt.broadcast` chunks are still
    delivered).

    Usage:
    ```python
    stream = rt.astream(agent, user_input="Write a short poem about rain.")
    async for chunk in stream:
        print(chunk, end="", flush=True)   # str token chunks
    final = stream.result                  # the complete StringResponse
    ```

    When you only care about the final result of the streamed run:
    ```python
    final = await rt.astream(agent, user_input="...")
    ```

    To consume a single named channel, chain `on_channel` on the returned handle (channel
    selection is a method, not a keyword argument, because `astream` forwards its keywords to
    the node — see `Stream.on_channel`):
    ```python
    async for chunk in rt.astream(node, topic="x").on_channel("final"):
        ...
    ```

    Args:
        node_: The node to invoke. This can be a node class or a function decorated with
            `@function_node` (same as `rt.call`).
        *args: The positional arguments to pass to the node.
        **kwargs: The keyword arguments to pass to the node.

    Returns:
        Stream[_TOutput]: An async iterator over the chunks, with the final result available
            via `.result` (or by awaiting the stream).
    """
    node: type[Node[_P, _TOutput]]

    # local import to prevent circular import issues (mirrors rt.call)
    from railtracks.built_nodes.concrete import RTFunction

    if isinstance(node_, RTFunction):
        node = extract_node_from_function(node_)
    else:
        node = node_

    return Stream(node, args, kwargs)
