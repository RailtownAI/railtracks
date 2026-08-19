"""Two-stage flow invocation: `Flow.connect()` returns a `FlowConnection`."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, List, ParamSpec, TypeVar

from railtracks._session import Session
from railtracks.interaction._call import call

if TYPE_CHECKING:
    from railtracks.context.external import MutableExternalContext
    from railtracks.llm.history import MessageHistory

    from .flow import Flow

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


@dataclass(frozen=True)
class NodeMessageHistory:
    """
    One node's conversation with its model.

    Args:
        node_name: Node that held the conversation, or
            `"<unknown>"` if cannot resolve type.
        node_id: Identifier of that node within the run.
        request_id: Identifier of the request that produced it.
        message_history: The messages exchanged, system prompt first.
    """

    node_name: str
    node_id: str
    request_id: str
    message_history: MessageHistory


class FlowConnection(Generic[_P, _TOutput]):
    """
    A connection to a flow, through which it can be invoked.

    Same invoke and behaviour as `Flow` object.
    """

    def __init__(self, flow: Flow[_P, _TOutput]) -> None:
        self._flow = flow
        self._session: Session | None = None
        self._in_flight = False

    async def ainvoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        """
        Runs the flow, leaving its context reachable on this connection.

        Raises:
            RuntimeError: If this connection is already running an invocation.
        """
        if self._in_flight:
            raise RuntimeError(
                "This connection is already running an invocation. A connection "
                "handles one at a time\n use a separate `flow.connect()`"
            )

        flow = self._flow
        self._in_flight = True
        try:
            with Session(
                context=deepcopy(flow._context),
                flow_name=flow.name,
                flow_id=flow.equality_hash(),
                name=None,
                timeout=flow._timeout,
                end_on_error=flow._end_on_error,
                broadcast_callback=flow._broadcast_callback,
                save_state=flow._save_state,
                payload_callback=flow._payload_callback,
            ) as session:
                # bound before the entry point runs, so the context of a failed
                # invocation is still reachable afterwards
                self._session = session
                return await call(flow.entry_point, *args, **kwargs)
        finally:
            self._in_flight = False

    def invoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        """
        Synchronous `ainvoke`.

        Note:
            When no event loop is running, blocks until the flow finishes.
            When called from inside a running event loop (e.g. a notebook or
            async framework), the run is dispatched to a worker thread with its
            own event loop; `contextvars.copy_context()` keeps Session and
            logging context visible there.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.ainvoke(*args, **kwargs))

        ctx = contextvars.copy_context()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(ctx.run, asyncio.run, self.ainvoke(*args, **kwargs))
            return future.result()

    @property
    def connected(self) -> bool:
        """Whether this connection has begun an invocation yet."""
        return self._session is not None

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError(
                "Nothing has run on this connection yet, so it has no context to read.\n"
                "\n"
                "Ensure FlowConnection is invoked instead of base Flow instance:\n"
                "\n"
                "    conn = flow.connect()\n"
                '    result = await conn.ainvoke("text") # NOT flow.ainvoke if context is desired\n'
                '    conn.context.get("progress")\n'
            )
        return self._session

    @property
    def context(self) -> MutableExternalContext:
        """
        The context of the most recent invocation.

        A live reference, not a copy. Context is not intended to be modified.

        """
        return self._require_session().context

    @property
    def session_id(self) -> str:
        """Identifier of the session backing the most recent invocation."""
        return self._require_session().identifier

    @property
    def session(self) -> Session:
        """
        The session backing the most recent invocation, for inspection.

        Already closed; the connection owns its lifecycle. `Session.payload()`
        and `Session.info` expose the run's state representation.
        """
        return self._require_session()

    def message_histories(self) -> List[NodeMessageHistory]:
        """
        Every model conversation from the most recent invocation, in the order the
        runs were recorded. Concurrently called nodes have no guaranteed order.

        Covers nested agents, unlike an `LLMResponse`, which carries only its
        own. Nodes that made no model calls are omitted.

        Walks the run's requests on every call rather than caching, so hold the
        result if you need it more than once.

            for h in conn.message_histories():
                print(h.node_name, len(h.message_history))

        Returns:
            List[NodeMessageHistory]: One entry per node that called a model.
        """
        info = self._require_session().info
        node_forest = info.node_forest

        histories: List[NodeMessageHistory] = []
        # a request is inserted into the heap when it is opened
        for request in info.request_forest.heap().values():
            history = getattr(request.output, "message_history", None)
            if history is None:
                continue
            node_type = node_forest.get_node_type(request.sink_id)
            histories.append(
                NodeMessageHistory(
                    node_name=node_type.name()
                    if node_type is not None
                    else "<unknown>",
                    node_id=request.sink_id,
                    request_id=request.identifier,
                    message_history=history,
                )
            )

        return histories

    def __repr__(self) -> str:
        if self._session is None:
            return f"FlowConnection(flow={self._flow.name!r}, not yet invoked)"
        return (
            f"FlowConnection(flow={self._flow.name!r}, session_id={self.session_id!r})"
        )
