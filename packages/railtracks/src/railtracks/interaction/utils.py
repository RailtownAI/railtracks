"""What `rt.call` and `rt.astream` share: making a request, recognising its completion,
and what a top-level request does around its run."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from railtracks.context.central import (
    get_current_scope,
    get_local_config,
    get_parent_id,
    get_run_id,
    get_session_identity,
)
from railtracks.events.context import (
    ContextCompletion,
    ContextCreation,
    emit_snapshot,
)
from railtracks.events.send import emit
from railtracks.events.session import SessionCompleted, SessionStarted, format_error
from railtracks.exceptions._base import is_fatal
from railtracks.pubsub.messages import (
    FatalFailure,
    RequestCompletionMessage,
    RequestCreation,
    RequestFinishedBase,
)

if TYPE_CHECKING:
    from railtracks.nodes.nodes import Node


def request_creation(
    request_id: str,
    node: type[Node],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    stream_queue: asyncio.Queue[Any] | None = None,
) -> RequestCreation:
    """The message that asks for ``node`` to run, made from inside the current scope."""
    return RequestCreation(
        current_node_id=get_parent_id(),
        current_run_id=get_run_id(),
        current_scope=get_current_scope(),
        new_request_id=request_id,
        running_mode="async",
        new_node_type=node,
        args=args,
        kwargs=kwargs,
        stream_queue=stream_queue,
    )


def regular_message_filter(request_id: str):
    """
    Returns a filter function that checks if the message matches the request ID.
    """

    def filter_func(item: RequestCompletionMessage) -> bool:
        if isinstance(item, RequestFinishedBase):
            return item.request_id == request_id
        return False

    return filter_func


def top_level_message_filter(request_id: str):
    """
    Returns a filter function that checks if the message matches the request ID, or is a
    fatal failure that ends the whole run.
    """

    def message_filter(item: RequestCompletionMessage) -> bool:
        # we want to filter and collect the message that matches this request_id
        matches_request_id = (
            isinstance(item, RequestFinishedBase) and item.request_id == request_id
        )
        fatal_failure = isinstance(item, FatalFailure)

        return matches_request_id or fatal_failure

    return message_filter


async def begin_top_level(node: type[Node]) -> float:
    """Announces a top-level request; returns its start time."""
    config = get_local_config()
    identity = get_session_identity()

    await emit(
        SessionStarted(
            session_id=identity.session_id,
            flow_name=identity.flow_name,
            flow_id=identity.flow_id,
            session_name=identity.session_name,
            entry_point_name=node.name() if hasattr(node, "name") else "Unknown",
            timeout=config.timeout,
            end_on_error=config.end_on_error,
            save_state=config.save_state,
        )
    )
    await emit_snapshot(ContextCreation)
    return time.perf_counter()


async def end_top_level(start_time: float, error: BaseException | None) -> None:
    """Announces how a top-level request ended."""
    await emit_snapshot(ContextCompletion)
    await emit(
        SessionCompleted(
            session_id=get_session_identity().session_id,
            status="success" if error is None else "failure",
            error=None if error is None else format_error(error),
            duration_seconds=time.perf_counter() - start_time,
            fatal=error is not None
            and (get_local_config().end_on_error or is_fatal(error)),
        )
    )
