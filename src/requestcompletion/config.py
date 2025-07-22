from __future__ import annotations

import os
import uuid
from typing import Callable, Coroutine

from .utils.logging.config import allowable_log_levels


class ExecutorConfig:
    def __init__(
        self,
        *,
        timeout: float = 150.0,
        end_on_error: bool = False,
        logging_setting: allowable_log_levels = "REGULAR",
        log_file: str | os.PathLike | None = None,
        subscriber: (
            Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
        ) = None,
        run_identifier: str | None = None,
        prompt_injection: bool = True,
        save_state: bool = True,
    ):
        """
        ExecutorConfig is special configuration object designed to allow customization of the executor in the RC system.

        Args:
            timeout (float): The maximum number of seconds to wait for a response to your top level request
            end_on_error (bool): If true, the executor will stop execution when an exception is encountered.
            logging_setting (allowable_log_levels): The setting for the level of logging you would like to have.
            log_file (str | os.PathLike | None): The file to which the logs will be written. If None, no file will be created.
            run_identifier (str | None): You can specify a run identifier to be used for this run. If None, a random UUID will be generated.
            subscriber (Callable or Coroutine): A function or coroutine that will handle streaming messages.
            prompt_injection (bool): If true, prompts can be injected with global context
            save_state (bool): If true, the state of the executor will be saved to disk.
        """
        self.timeout = timeout
        self.end_on_error = end_on_error
        self.logging_setting = logging_setting
        self.subscriber = subscriber
        self.run_identifier = run_identifier if run_identifier else str(uuid.uuid4())
        self.log_file = log_file
        self.prompt_injection = prompt_injection
        self.save_state = save_state
