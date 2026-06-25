from __future__ import annotations

import asyncio
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
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
    is_context_active,
    is_context_present,
)
from railtracks.exceptions import GlobalTimeOutError
from railtracks.nodes.utils import extract_node_from_function
from railtracks.pubsub.messages import (
    FatalFailure,
    RequestCompletionMessage,
    RequestCreation,
    RequestFinishedBase,
)
from railtracks.pubsub.utils import output_mapping

if TYPE_CHECKING:
    from railtracks.built_nodes.concrete import RTFunction
    from railtracks.nodes.nodes import Node

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")

_BroadcastCallback = (
    Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _resolve_node(
    node_: type[Node[_P, _TOutput]] | RTFunction[_P, _TOutput],
) -> type[Node[_P, _TOutput]]:
    """Normalise an :class:`RTFunction` wrapper to its underlying :class:`Node` class."""
    if hasattr(node_, "node_type"):
        from railtracks.built_nodes.concrete import RTFunction as _RTFunction  # lazy — circular

        assert isinstance(node_, _RTFunction)
        return extract_node_from_function(node_)
    return node_  # type: ignore[return-value]


def _make_message_filter(
    request_id: str,
    *,
    top_level: bool,
) -> Callable[[RequestCompletionMessage], bool]:
    """Return a pub/sub predicate for *request_id*.

    When *top_level* is ``True``, :class:`~railtracks.pubsub.messages.FatalFailure`
    messages are also accepted so the top-level waiter surfaces fatal errors.
    """

    def _filter(item: RequestCompletionMessage) -> bool:
        matches = isinstance(item, RequestFinishedBase) and item.request_id == request_id
        return matches or (top_level and isinstance(item, FatalFailure))

    return _filter


async def _execute(
    node: type[Node[_P, _TOutput]],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    top_level: bool,
) -> _TOutput:
    publisher = get_publisher()
    request_id = str(uuid4())

    # Register the listener *before* publishing to avoid missing the completion event.
    f = publisher.listener(_make_message_filter(request_id, top_level=top_level), output_mapping)

    await publisher.publish(
        RequestCreation(
            current_node_id=get_parent_id(),
            current_run_id=get_run_id(),
            new_request_id=request_id,
            running_mode="async",
            new_node_type=node,
            args=args,
            kwargs=kwargs,
        )
    )

    return await f


async def _start(
    node: type[Node[_P, _TOutput]],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> _TOutput:
    """Top-level execution: activates the publisher and enforces the session timeout."""
    await activate_publisher()

    # asyncio.wait_for raises TimeoutError for both its own deadline and errors
    # that bubble up from inside the coroutine.  Track which case we're in so we
    # can re-raise user-originated TimeoutErrors unchanged rather than wrapping
    # them as GlobalTimeOutError.
    user_raised_timeout = False

    async def _guarded() -> _TOutput:
        nonlocal user_raised_timeout
        try:
            return await _execute(node, args, kwargs, top_level=True)
        except asyncio.TimeoutError:
            user_raised_timeout = True
            raise

    timeout = get_local_config().timeout
    try:
        return await asyncio.wait_for(_guarded(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        if user_raised_timeout:
            raise
        raise GlobalTimeOutError(timeout=timeout) from exc


# ── public API ────────────────────────────────────────────────────────────────


@overload
async def call(
    node_: type[Node[_P, _TOutput]],
    *args: _P.args,
    broadcast_callback: _BroadcastCallback = ...,
    **kwargs: _P.kwargs,
) -> _TOutput: ...


@overload
async def call(
    node_: RTFunction[_P, _TOutput],
    *args: _P.args,
    broadcast_callback: _BroadcastCallback = ...,
    **kwargs: _P.kwargs,
) -> _TOutput: ...


async def call(
    node_: type[Node[_P, _TOutput]] | RTFunction[_P, _TOutput],
    *args: _P.args,
    broadcast_callback: _BroadcastCallback = None,
    **kwargs: _P.kwargs,
) -> _TOutput:
    """Call a node and return its result.

    Usage::

        # sequential
        result = await call(NodeA, "hello world", 42)

        # parallel
        results = await asyncio.gather(*[call(NodeA, "hello world", i) for i in range(10)])

        # push streaming — callback receives each str chunk in real time
        chunks: list[str] = []
        result = await call(agent, user_input="hi", broadcast_callback=chunks.append)

    Args:
        node_: The node or ``@function_node`` / ``@agent_node`` to call.
        *args: Positional arguments forwarded to the node.
        broadcast_callback: Optional callable invoked with each ``str`` chunk as it
            arrives.  Accepts both sync ``(str) -> None`` and async
            ``(str) -> Coroutine`` callables.  Only applied when ``call()``
            creates its own execution context (i.e., no active context).
        **kwargs: Keyword arguments forwarded to the node.
    """
    node = _resolve_node(node_)

    if not is_context_present():
        from railtracks import Session  # lazy — avoids circular import

        with Session(broadcast_callback=broadcast_callback):
            return await _start(node, args, kwargs)

    if not is_context_active():
        return await _start(node, args, kwargs)

    return await _execute(node, args, kwargs, top_level=False)


@overload
async def astream(
    node_: type[Node[_P, _TOutput]],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> AsyncGenerator[str | _TOutput, None]: ...


@overload
async def astream(
    node_: RTFunction[_P, _TOutput],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> AsyncGenerator[str | _TOutput, None]: ...


async def astream(
    node_: type[Node[_P, _TOutput]] | RTFunction[_P, _TOutput],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> AsyncGenerator[str | _TOutput, None]:
    """Streaming counterpart of :func:`call` — yields chunks then the terminal result.

    Yields each ``str`` chunk in real time as the node produces them, then yields
    the terminal response (``StringResponse`` / ``StructuredResponse``) as the
    final item.

    Use anywhere you would use :func:`call` but want real-time chunks. No
    :class:`~railtracks.orchestration.flow.Flow` wrapper required.

    Example::

        async for item in rt.astream(agent, user_input="Hello"):
            if isinstance(item, str):
                print(item, end="", flush=True)
            else:
                final = item  # StringResponse

    Args:
        node_: The node or ``@function_node`` / ``@agent_node`` to stream.
        *args: Positional arguments forwarded to the node.
        **kwargs: Keyword arguments forwarded to the node.

    Yields:
        ``str`` chunks in arrival order, then the terminal response object.
    """
    from railtracks import Session  # lazy — avoids circular import

    node = _resolve_node(node_)
    queue: asyncio.Queue[Any] = asyncio.Queue()

    async def _enqueue_chunk(chunk: str) -> None:
        await queue.put(chunk)

    async def _produce() -> None:
        try:
            with Session(broadcast_callback=_enqueue_chunk):
                result = await _start(node, args, kwargs)
            await queue.put(result)
        except Exception as exc:
            await queue.put(exc)

    task = asyncio.create_task(_produce())

    while True:
        item = await queue.get()
        if isinstance(item, BaseException):
            task.cancel()
            raise item
        yield item
        if not isinstance(item, str):
            break

    await task
