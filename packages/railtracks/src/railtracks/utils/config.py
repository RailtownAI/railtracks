from __future__ import annotations

import os
from typing import Callable, Coroutine

from railtracks.utils.logging.config import AllowableLogLevels, str_to_log_level


class ExecutorConfig:
    def __init__(
        self,
        *,
        timeout: float = 150.0,
        end_on_error: bool = False,
        logging_setting: AllowableLogLevels = "INFO",
        log_file: str | os.PathLike | None = None,
        broadcast_callback: (
            Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
        ) = None,
        prompt_injection: bool = True,
        save_state: bool = True,
    ):
        """
        ExecutorConfig is special configuration object designed to allow customization of the executor in the RT system.

        Args:
            timeout (float): The maximum number of seconds to wait for a response to your top level request
            end_on_error (bool): If true, the executor will stop execution when an exception is encountered.
            logging_setting (AllowableLogLevels): The setting for the level of logging you would like to have.
            log_file (str | os.PathLike | None): The file to which the logs will be written. If None, no file will be created.
            broadcast_callback (Callable or Coroutine): A function or coroutine that will handle streaming messages.
            prompt_injection (bool): If true, prompts can be injected with global context
            save_state (bool): If true, the state of the executor will be saved to disk.
        """
        self.timeout = timeout
        self.end_on_error = end_on_error
        self.logging_setting = logging_setting
        self.subscriber = broadcast_callback
        self.log_file = log_file
        self.prompt_injection = prompt_injection
        self.save_state = save_state

    @property
    def logging_setting(self) -> AllowableLogLevels:
        return self._logging_setting

    @logging_setting.setter
    def logging_setting(self, value: AllowableLogLevels):
        if value not in str_to_log_level:
            raise ValueError(
                f"logging_setting must be one of {str_to_log_level}, got {value}"
            )
        self._logging_setting: AllowableLogLevels = value

    def precedence_overwritten(
        self,
        *,
        timeout: float | None = None,
        end_on_error: bool | None = None,
        logging_setting: AllowableLogLevels | None = None,
        log_file: str | os.PathLike | None = None,
        subscriber: (
            Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
        ) = None,
        prompt_injection: bool | None = None,
        save_state: bool | None = None,
    ):
        """
        If any of the parameters are provided (not None), it will create a new update the current instance with the new values and return a deep copied reference to it.
        """
        return ExecutorConfig(
            timeout=timeout if timeout is not None else self.timeout,
            end_on_error=end_on_error
            if end_on_error is not None
            else self.end_on_error,
            logging_setting=logging_setting
            if logging_setting is not None
            else self.logging_setting,
            log_file=log_file if log_file is not None else self.log_file,
            broadcast_callback=subscriber
            if subscriber is not None
            else self.subscriber,
            prompt_injection=prompt_injection
            if prompt_injection is not None
            else self.prompt_injection,
            save_state=save_state if save_state is not None else self.save_state,
        )

    def __repr__(self):
        return (
            f"ExecutorConfig(timeout={self.timeout}, end_on_error={self.end_on_error}, "
            f"logging_setting={self.logging_setting}, log_file={self.log_file}, "
            f"prompt_injection={self.prompt_injection}, "
            f"save_state={self.save_state})"
        )
