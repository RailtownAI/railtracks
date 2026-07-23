from __future__ import annotations

import asyncio
import time
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Generator,
    Generic,
    NoReturn,
    ParamSpec,
    TypeVar,
    cast,
)
from uuid import uuid4

from railtracks.context.central import (
    activate_publisher,
    get_local_config,
    get_parent_id,
    get_publisher,
    get_run_id,
    is_context_present,
)
from railtracks.exceptions import GlobalTimeOutError
from railtracks.nodes.utils import extract_node_from_function
from railtracks.pubsub.messages import (
    FatalFailure,
    RequestCompletionMessage,
    RequestCreation,
    RequestFinishedBase,
    Streaming,
)
from railtracks.pubsub.utils import output_mapping
from railtracks.utils.logging import get_rt_logger

if TYPE_CHECKING:
    from railtracks._session import Session
    from railtracks.built_nodes.function.base import RTFunction
    from railtracks.nodes.nodes import Node

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")

logger = get_rt_logger(__name__)

# sentinel used to mark "no result yet" (None is a valid node result)
_UNSET = object()


class Stream(Generic[_TOutput], AsyncIterator[Any]):
    """
    The handle returned by `rt.astream(...)`.

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
        on_start: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
    ):
        """
        Creates a new (not yet started) streamed invocation. Prefer `rt.astream(...)` over
        constructing this directly.

        Args:
            node: The node type to invoke.
            args: The positional arguments to pass to the node.
            kwargs: The keyword arguments to pass to the node.
            on_start: Called once, just before the run is launched on first iteration. The
                caller (`rt.astream`) uses this to set up the surrounding run context (e.g.
                open a session when there is none). The `Stream` itself owns no such state.
            on_close: Called once when the run finishes (or errors, or times out). The caller
                uses this to tear down whatever `on_start` set up. The two are paired so a
                `Stream` never has to know about — or reach into — a session's lifecycle.
        """
        self._node = node
        self._args = args
        self._kwargs = kwargs

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
        # run-context hooks supplied by the caller (session setup/teardown lives there,
        # not in the Stream — see rt.astream)
        self._on_start = on_start
        self._on_close = on_close
        self._closed = False

    # ------------------------------------------------------------------ lifecycle

    async def _start(self) -> None:
        """Lazily starts the run on first iteration: subscribes to the bus, then publishes
        the entry request with streaming enabled."""
        if self._started:
            return
        self._started = True

        # let the caller set up the run context (e.g. open a session); the Stream stays
        # out of session lifecycle entirely.
        if self._on_start is not None:
            self._on_start()

        await activate_publisher()
        publisher = get_publisher()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        self._queue = queue

        request_id = self._request_id

        def _subscriber(message: RequestCompletionMessage) -> None:
            if isinstance(message, Streaming):
                if message.stream_id == request_id:
                    queue.put_nowait(("chunk", message.streamed_object))
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
        """Unsubscribes from the bus and hands teardown of the run context back to the caller."""
        if self._sub_id is not None:
            try:
                get_publisher().unsubscribe(self._sub_id)
            except Exception:
                # the publisher may already be gone (e.g. session shut down); nothing to do.
                logger.debug("Failed to unsubscribe astream subscriber.", exc_info=True)
            self._sub_id = None

        # tear down whatever on_start set up (e.g. a session); run at most once.
        if not self._closed:
            self._closed = True
            if self._on_close is not None:
                self._on_close()

    # ------------------------------------------------------------------ iteration

    def __aiter__(self) -> Stream[_TOutput]:
        return self

    async def __anext__(self) -> Any:
        """Returns the next chunk, or raises `StopAsyncIteration` once the run finishes
        (resolving `.result`), or the node's error / `GlobalTimeOutError`."""
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
            return payload
        else:
            # the run has finished: resolve the final result (or raise the node's error)
            self._finished = True
            self._cleanup()
            try:
                self._result = output_mapping(payload)
            except BaseException as e:
                self._error = e
                raise
            raise StopAsyncIteration

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


def astream(
    node_: type[Node[_P, _TOutput]] | RTFunction[_P, _TOutput],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> Stream[_TOutput]:
    """
    Invoke a node with streaming enabled and return a `Stream` over its emitted chunks.

    This is the streaming entry point of railtracks. The same node/agent object serves
    streaming and non-streaming runs — `rt.call` runs it buffered, `rt.astream` streams it.
    Streaming is frame-local: only the node you invoke here streams its LLM responses;
    nested `rt.call` children run buffered.

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

    if hasattr(node_, "node_type"):
        # local import to prevent circular import issues (mirrors rt.call)
        from railtracks.built_nodes.function.base import RTFunction

        assert isinstance(node_, RTFunction)
        node = extract_node_from_function(node_)
    else:
        # not an RTFunction (no `node_type`), so it is already a Node subclass
        node = cast("type[Node[_P, _TOutput]]", node_)

    # Session lifecycle is owned here, not by the Stream handle. When called outside any
    # session we open one and hold it in this closure; the Stream calls `_close` back once
    # it finishes (see Stream.on_start / on_close), so the session's open/close logic lives
    # with astream rather than inside the returned object.
    owned: list[Session] = []

    def _open() -> None:
        if not is_context_present():
            from railtracks import Session  # lazy import to avoid a circular import

            owned.append(Session())

    def _close() -> None:
        while owned:
            owned.pop().__exit__(None, None, None)

    return Stream(node, args, kwargs, on_start=_open, on_close=_close)
