from __future__ import annotations

import os
from typing import Any, Callable, Mapping

# A stream callback is either a single callable invoked for every chunk, or a mapping of
# channel name -> callable used to route chunks per channel. Callables may be sync or async.
StreamCallback = Callable[[Any], Any] | Mapping[str, Callable[[Any], Any]]


class ExecutorConfig:
    def __init__(
        self,
        *,
        timeout: float | None = None,
        end_on_error: bool = False,
        stream_callback: StreamCallback | None = None,
        prompt_injection: bool = True,
        save_state: bool = True,
        payload_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        """
        ExecutorConfig is special configuration object designed to allow customization of the executor in the RT system.

        Args:
            timeout (float | None): The maximum number of seconds to wait for a response to your top level request. Pass None (or omit) to disable the timeout entirely.
            end_on_error (bool): If true, the executor will stop execution when an exception is encountered.
            stream_callback (Callable or Mapping[str, Callable]): A callback (or mapping of channel
                name -> callback) that receives every streamed/broadcast item. Providing it also
                enables token streaming for top-level calls (push-mode streaming; see `rt.astream`
                for pull-mode).
            prompt_injection (bool): If true, prompts can be injected with global context
            save_state (bool): If true, the state of the executor will be saved to disk.
            payload_callback (Callable): A callback invoked once at session end with the full
                serialized session payload.
        """
        self.timeout = timeout
        self.end_on_error = end_on_error
        self.stream_subscriber = stream_callback
        self.prompt_injection = prompt_injection
        # During test runs, disable save_state by default unless RAILTRACKS_ALLOW_PERSISTENCE is set
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
        return self._user_save_state

    def precedence_overwritten(
        self,
        *,
        timeout: float | None = None,
        end_on_error: bool | None = None,
        stream_subscriber: StreamCallback | None = None,
        prompt_injection: bool | None = None,
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
            stream_callback=stream_subscriber
            if stream_subscriber is not None
            else self.stream_subscriber,
            prompt_injection=prompt_injection
            if prompt_injection is not None
            else self.prompt_injection,
            save_state=save_state if save_state is not None else self.save_state,
            payload_callback=payload_callback
            if payload_callback is not None
            else self.payload_callback,
        )

    def __repr__(self):
        return (
            f"ExecutorConfig(timeout={self.timeout}, end_on_error={self.end_on_error}, "
            f"prompt_injection={self.prompt_injection}, "
            f"save_state={self.save_state}, payload_callback={self.payload_callback})"
        )
