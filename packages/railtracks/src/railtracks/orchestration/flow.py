from __future__ import annotations

import asyncio
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
    """
    Initializes a Flow object with a provided entry point and a unique name.

    A flow object is the configuration where you can run your agent with different input arguments.

    Args:
        name (str): A unique name for the flow. This is used for logging and state management.
        entry_point (Callable | RTSyncFunction | RTAsyncFunction): The starting point of your flow.
        context (dict[str, Any], optional): Context to be passed to all instantiations (or runs) of this flow. Note that the context can be overridden at invocation time.
        timeout (float, optional): The maximum number of seconds to wait for a response to your top-level request.
        end_on_error (bool, optional): If True, the execution will stop when an exception is encountered.
        broadcast_callback (Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None, optional): A callback function that will be called with the broadcast messages.
        prompt_injection (bool, optional): If True, the prompt will be automatically injected from context variables.
        save_state (bool, optional): If True, the state of the execution will be saved to a file at the end of the run in the `.railtracks/data/sessions/` directory.
        payload_callback (Callable[[dict[str, Any]], None], optional): A callback function that will run upon completion of the flow with the final payload as an argument.
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
        """
        Creates a new Flow with the updated context. Note this will include the previous context values.
        """
        new_obj = deepcopy(self)
        new_obj._context.update(context)
        return new_obj

    async def ainvoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _TOutput:
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
        try:
            return asyncio.run(self.ainvoke(*args, **kwargs))

        except RuntimeError:
            raise RuntimeError(
                "Cannot invoke flow synchronously within an active event loop. Use 'ainvoke' instead."
            )

    def equality_hash(self) -> str:
        """
        Generates a hash based on the flow's configuration for equality checks.
        """
        config_string = json.dumps(self._get_hash_content(), sort_keys=True)
        return hashlib.sha256(config_string.encode()).hexdigest()

    def _get_hash_content(self) -> dict:
        return {
            "name": self.name,
        }
