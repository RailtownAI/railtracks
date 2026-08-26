from __future__ import annotations

import os
import warnings
from typing import Any, Callable, Coroutine


class ExecutorConfig:
    def __init__(
        self,
        *,
        timeout: float | None = None,
        end_on_error: bool = False,
        broadcast_callback: (
            Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
        ) = None,
        save_state: bool | None = None,
        payload_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        """
        ExecutorConfig is special configuration object designed to allow customization of the executor in the RT system.

        Args:
            timeout (float | None): The maximum number of seconds to wait for a response to your top level request. Pass None (or omit) to disable the timeout entirely.
            end_on_error (bool): If true, the executor will stop execution when an exception is encountered.
            broadcast_callback (Callable or Coroutine): A function or coroutine that receives items published with `rt.broadcast`.
            save_state (bool | None): If true, the executor state is saved to disk at the end of the run. Pass None (or omit) to use the current implicit default (True); a DeprecationWarning fires and the default flips to False in the next release.
        """
        self.timeout = timeout
        self.end_on_error = end_on_error
        self.subscriber = broadcast_callback
        self._user_save_state = save_state

        self.payload_callback = payload_callback

    # this is done because if we try to lock the save_state in init
    # later when we want to allow a few tests to actually run persistance, they wont be able to do so
    @property
    def save_state(self) -> bool:
        if os.getenv("RAILTRACKS_TEST_MODE") and not os.getenv(
            "RAILTRACKS_ALLOW_PERSISTENCE"
        ):
            return False
        if self._user_save_state is not None:
            warnings.warn(
                "The save_state parameter is deprecated and will be removed in "
                "a future release. The .railtracks/data/sessions/*.json dump is "
                "being replaced by the event stream (.railtracks/data/events/). "
                "Remove the save_state argument to let the framework default "
                "take over; the default flips from True to False next release.",
                DeprecationWarning,
                stacklevel=3,
            )
            return self._user_save_state
        return True

    def _save_state_silently(self) -> bool:
        """Resolved save_state without emitting the deprecation warning.

        For internal telemetry paths that need the value but shouldn't be the
        thing that surfaces the deprecation to users.
        """
        if os.getenv("RAILTRACKS_TEST_MODE") and not os.getenv(
            "RAILTRACKS_ALLOW_PERSISTENCE"
        ):
            return False
        return True if self._user_save_state is None else self._user_save_state

    def precedence_overwritten(
        self,
        *,
        timeout: float | None = None,
        end_on_error: bool | None = None,
        subscriber: (
            Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
        ) = None,
        save_state: bool | None = None,
        payload_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        """
        If any of the parameters are provided (not None), it will create a new update the current instance with the new values and return a deep copied reference to it.
        """
        return ExecutorConfig(
            timeout=timeout,
            end_on_error=end_on_error
            if end_on_error is not None
            else self.end_on_error,
            broadcast_callback=subscriber
            if subscriber is not None
            else self.subscriber,
            save_state=save_state if save_state is not None else self._user_save_state,
            payload_callback=payload_callback
            if payload_callback is not None
            else self.payload_callback,
        )

    def __repr__(self):
        return (
            f"ExecutorConfig(timeout={self.timeout}, end_on_error={self.end_on_error}, "
            f"save_state={self._user_save_state}, payload_callback={self.payload_callback})"
        )
