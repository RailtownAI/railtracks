from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import hashlib
import json
from copy import deepcopy
from typing import Any, Callable, Coroutine, Generic, ParamSpec, TypeVar

from railtracks._session import Session
from railtracks.built_nodes.concrete.function_base import (
    RTAsyncFunction,
    RTSyncFunction,
)
from railtracks.interaction._call import call

from ..nodes.nodes import Node

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


class Flow(Generic[_P, _TOutput]):
    """A reusable, configured entry point for running an agent graph.

    A ``Flow`` binds an entry-point node to a fixed set of runtime options
    (context, timeout, callbacks, etc.) so the same configuration can be
    invoked repeatedly without repeating arguments.  Each invocation is fully
    isolated — flows never share state between runs.

    Typical usage::

        flow = Flow("my-agent", entry_point=my_node, context={"user": "alice"})

        # async (preferred — native event loop, no overhead)
        result = await flow.ainvoke(query)

        # sync (works in scripts and Jupyter; dispatches to a worker thread
        # when an event loop is already running)
        result = flow.invoke(query)

    Args:
        name: Unique human-readable name used in logging and state filenames.
        entry_point: The node (or decorated function) that starts the graph.
        context: Key/value pairs made available to every node via
            ``rt.context`` for the duration of the run.  Deep-copied at
            invocation time so mutations inside a run never affect later runs.
        timeout: Maximum seconds to wait for the top-level call to complete.
            ``None`` means no limit.
        end_on_error: When ``True``, the first unhandled exception aborts the
            run immediately.
        broadcast_callback: Called with each broadcast string emitted by
            ``rt.broadcast()``.  May be sync or async.
        prompt_injection: When ``True``, prompt text is automatically injected
            from context variables before the run starts.
        save_state: When ``True``, the session state is persisted to
            ``.railtracks/data/sessions/`` after the run completes.
        payload_callback: Called with the final result payload once the run
            finishes successfully.
    """

    def __init__(
        self,
        name: str,
        entry_point: (
            Callable[_P, Node[_TOutput]]
            | RTSyncFunction[_P, _TOutput]
            | RTAsyncFunction[_P, _TOutput]
        ),
        *,
        context: dict[str, Any] | None = None,
        timeout: float | None = None,
        end_on_error: bool | None = None,
        broadcast_callback: (
            Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
        ) = None,
        prompt_injection: bool | None = None,
        save_state: bool | None = None,
        payload_callback: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.entry_point: Callable[_P, Node[_TOutput]]

        if hasattr(entry_point, "node_type"):
            self.entry_point = entry_point.node_type
        else:
            self.entry_point = entry_point

        self.name = name
        self._context: dict[str, Any] = context or {}
        self._timeout = timeout
        self._end_on_error = end_on_error
        self._broadcast_callback = broadcast_callback
        self._prompt_injection = prompt_injection
        self._save_state = save_state
        self._payload_callback = payload_callback

    def update_context(self, context: dict[str, Any]) -> Flow[_P, _TOutput]:
        """Return a new Flow with additional context values merged in.

        The original flow is not modified.  Values in ``context`` override
        any existing keys; keys not present in ``context`` are preserved.

        Args:
            context: Entries to add or override in the flow's context.

        Returns:
            A new :class:`Flow` instance with the merged context.
        """
        new_obj = deepcopy(self)
        new_obj._context.update(context)
        return new_obj

    async def ainvoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        """Run the flow asynchronously and return the entry-point result.

        Preferred invocation path — call it directly from any async context::

            result = await flow.ainvoke(arg1, arg2)

        Each call is fully isolated: context is deep-copied at the start so
        mutations inside the run never affect subsequent calls or other
        concurrent runs.

        Args:
            *args: Positional arguments forwarded to the entry-point node.
            **kwargs: Keyword arguments forwarded to the entry-point node.

        Returns:
            The value returned by the entry-point node.
        """
        with Session(
            context=deepcopy(self._context),
            flow_name=self.name,
            flow_id=self.equality_hash(),
            name=None,
            timeout=self._timeout,
            end_on_error=self._end_on_error,
            broadcast_callback=self._broadcast_callback,
            prompt_injection=self._prompt_injection,
            save_state=self._save_state,
            payload_callback=self._payload_callback,
        ):
            result = await call(self.entry_point, *args, **kwargs)

        return result

    def invoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        """Run the flow synchronously and return the entry-point result.

        Thin synchronous wrapper around :meth:`ainvoke`.  Behaviour depends
        on whether an event loop is already running in the current thread:

        - **No running loop** (plain script, ``pytest``, etc.) —
          delegates to ``asyncio.run()``, which creates a fresh event loop.
        - **Running loop** (Jupyter, FastAPI, async test runner) —
          submits the coroutine to a ``ThreadPoolExecutor`` running its own
          fresh event loop.  ``contextvars.copy_context()`` propagates the
          current context into the worker thread so all ContextVars are
          visible inside the run.

        .. note::
            Prefer ``await flow.ainvoke()`` in async contexts — ``invoke``
            adds thread-dispatch overhead and is provided as a convenience
            for callers that cannot use ``await``.

        Args:
            *args: Positional arguments forwarded to the entry-point node.
            **kwargs: Keyword arguments forwarded to the entry-point node.

        Returns:
            The value returned by the entry-point node.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.ainvoke(*args, **kwargs))

        ctx = contextvars.copy_context()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(ctx.run, asyncio.run, self.ainvoke(*args, **kwargs))
            return future.result()

    def equality_hash(self) -> str:
        """Return a stable hash that identifies this flow's configuration.

        Two flows with the same name produce the same hash regardless of
        other parameters (timeout, context, etc.).
        """
        config_string = json.dumps(self._get_hash_content(), sort_keys=True)
        return hashlib.sha256(config_string.encode()).hexdigest()

    def _get_hash_content(self) -> dict:
        return {
            "name": self.name,
        }
