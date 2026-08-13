from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import hashlib
import json
from copy import deepcopy
from typing import Any, Callable, Coroutine, Generic, ParamSpec, TypeVar

from railtracks.built_nodes.function.base import RTFunction

from ..nodes.nodes import Node
from .connection import FlowConnection

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


class Flow(Generic[_P, _TOutput]):
    """A reusable, configured entry point for running an agent graph.

    Binds an entry-point node to a fixed set of runtime options so the same
    configuration can be invoked repeatedly.  Each invocation is fully isolated.

    Typical usage::

        flow = Flow("my-agent", entry_point=my_node, context={"user": "alice"})
        result = await flow.ainvoke(query)  # async (preferred)
        result = flow.invoke(query)  # sync

    Args:
        name (str): A unique name for the flow. This is used for logging and state management.
        entry_point (Callable | RTSyncFunction | RTAsyncFunction): The starting point of your flow.
        context (dict[str, Any], optional): Context to be passed to all instantiations (or runs) of this flow. Note that the context can be overridden at invocation time.
        timeout (float, optional): The maximum number of seconds to wait for a response to your top-level request.
        end_on_error (bool, optional): If True, the execution will stop when an exception is encountered.
        broadcast_callback (Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None, optional): A passive listener for one-off events published with `rt.broadcast`.
        prompt_injection (bool, optional): If True, the prompt will be automatically injected from context variables.
        save_state (bool, optional): If True, the state of the execution will be saved to a file at the end of the run in the `.railtracks/data/sessions/` directory.
        payload_callback (Callable[[dict[str, Any]], None], optional): A callback function that will run upon completion of the flow with the final payload as an argument.
    """

    def __init__(
        self,
        name: str,
        entry_point: (type[Node[_P, _TOutput]] | RTFunction[_P, _TOutput]),
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
        self.entry_point: type[Node[_P, _TOutput]]

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

    def connect(self) -> FlowConnection[_P, _TOutput]:
        """
        Opens a connection to this flow.

        A `FlowConnection` invokes the flow exactly as `invoke`/`ainvoke` do, and
        additionally keeps the run's context reachable.

            conn = flow.connect()
            result = await conn.ainvoke("text") # not flow.ainvoke if context is desired

        Returns:
            FlowConnection: A connection to current flow.
        """
        return FlowConnection(self)

    async def ainvoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        return await self.connect().ainvoke(*args, **kwargs)

    def invoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
        return self.connect().invoke(*args, **kwargs)

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
