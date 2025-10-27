import inspect
import json
import os
import time
import uuid
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, ParamSpec, Tuple, TypeVar, overload

from railtracks.exceptions.messages.exception_messages import (
    ExceptionMessageKey,
    get_message,
)

from .context.central import (
    delete_globals,
    get_global_config,
    register_globals,
)
from .execution.coordinator import Coordinator
from .execution.execution_strategy import AsyncioExecutionStrategy
from .pubsub import RTPublisher, stream_subscriber
from .state.info import (
    ExecutionInfo,
)
from .state.state import RTState
from .utils.config import ExecutorConfig
from .utils.logging.config import (
    AllowableLogLevels,
    mark_session_logging_override,
    restore_module_logging,
)
from .utils.logging.create import get_rt_logger

logger = get_rt_logger("Session")

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


class Session:
    """
    The main class for managing an execution session.

    This class is responsible for setting up all the necessary components for running a Railtracks execution, including the coordinator, publisher, and state management.

    For the configuration parameters of the setting. It will follow this precedence:
    1. The parameters in the `Session` constructor.
    2. The parameters in global context variables.
    3. The default values.

    Default Values:
    - `name`: None
    - `timeout`: 150.0 seconds
    - `end_on_error`: False
    - `logging_setting`: "INFO"
    - `log_file`: None (logs will not be written to a file)
    - `broadcast_callback`: None (no callback for broadcast messages)
    - `prompt_injection`: True (the prompt will be automatically injected from context variables)
    - `save_state`: True (the state of the execution will be saved to a file at the end of the run in the `.railtracks` directory)


    Args:
        name (str | None, optional): Optional name for the session. This name will be included in the saved state file if `save_state` is True.
        context (Dict[str, Any], optional): A dictionary of global context variables to be used during the execution.
        timeout (float, optional): The maximum number of seconds to wait for a response to your top-level request.
        end_on_error (bool, optional): If True, the execution will stop when an exception is encountered.
        logging_setting (AllowableLogLevels, optional): The setting for the level of logging you would like to have. This will override the module-level logging settings for the duration of this session.
        log_file (str | os.PathLike | None, optional): The file to which the logs will be written.
        broadcast_callback (Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None, optional): A callback function that will be called with the broadcast messages.
        prompt_injection (bool, optional): If True, the prompt will be automatically injected from context variables.
        save_state (bool, optional): If True, the state of the execution will be saved to a file at the end of the run in the `.railtracks` directory.
    """

    def __init__(
        self,
        context: Dict[str, Any] | None = None,
        *,
        name: str | None = None,
        timeout: float | None = None,
        end_on_error: bool | None = None,
        logging_setting: AllowableLogLevels | None = None,
        log_file: str | os.PathLike | None = None,
        broadcast_callback: (
            Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
        ) = None,
        prompt_injection: bool | None = None,
        save_state: bool | None = None,
    ):
        # first lets read from defaults if nessecary for the provided input config

        self.executor_config = self.global_config_precedence(
            timeout=timeout,
            end_on_error=end_on_error,
            logging_setting=logging_setting,
            log_file=log_file,
            broadcast_callback=broadcast_callback,
            prompt_injection=prompt_injection,
            save_state=save_state,
        )

        if context is None:
            context = {}

        self.name = name

        self._has_custom_logging = logging_setting is not None or log_file is not None

        if self._has_custom_logging:
            mark_session_logging_override(
                session_level=self.executor_config.logging_setting,
                session_log_file=self.executor_config.log_file,
            )

        self.publisher: RTPublisher = RTPublisher()

        self._identifier = str(uuid.uuid4())

        executor_info = ExecutionInfo.create_new()
        self.coordinator = Coordinator(
            execution_modes={"async": AsyncioExecutionStrategy()}
        )
        self.rt_state = RTState(
            executor_info, self.executor_config, self.coordinator, self.publisher
        )

        self.coordinator.start(self.publisher)
        self._setup_subscriber()
        register_globals(
            session_id=self._identifier,
            rt_publisher=self.publisher,
            parent_id=None,
            executor_config=self.executor_config,
            global_context_vars=context,
        )

        self._start_time = time.time()

        logger.debug("Session %s is initialized" % self._identifier)

    @classmethod
    def global_config_precedence(
        cls,
        timeout: float | None,
        end_on_error: bool | None,
        logging_setting: AllowableLogLevels | None,
        log_file: str | os.PathLike | None,
        broadcast_callback: (
            Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
        ),
        prompt_injection: bool | None,
        save_state: bool | None,
    ) -> ExecutorConfig:
        """
        Uses the following precedence order to determine the configuration parameters:
        1. The parameters in the method parameters.
        2. The parameters in global context variables.
        3. The default values.
        """
        global_executor_config = get_global_config()

        return global_executor_config.precedence_overwritten(
            timeout=timeout,
            end_on_error=end_on_error,
            logging_setting=logging_setting,
            log_file=log_file,
            subscriber=broadcast_callback,
            prompt_injection=prompt_injection,
            save_state=save_state,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.executor_config.save_state:
            try:
                railtracks_dir = Path(".railtracks")
                railtracks_dir.mkdir(
                    exist_ok=True
                )  # Creates if doesn't exist, skips otherwise.

                # Try to create file path with name, fallback to identifier only if there's an issue
                try:
                    file_path = (
                        railtracks_dir / f"{self.name}_{self._identifier}.json"
                        if self.name
                        else railtracks_dir / f"{self._identifier}.json"
                    )
                    file_path.touch()
                except FileNotFoundError:
                    logger.warning(
                        get_message(
                            ExceptionMessageKey.INVALID_SESSION_FILE_NAME_WARN
                        ).format(name=self.name, identifier=self._identifier)
                    )
                    file_path = railtracks_dir / f"{self._identifier}.json"

                logger.info("Saving execution info to %s" % file_path)

                file_path.write_text(json.dumps(self.payload()))
            except Exception as e:
                logger.error(
                    "Error while saving to execution info to file",
                    exc_info=e,
                )

        self._close()

    def _setup_subscriber(self):
        """
        Prepares and attaches the saved broadcast_callback to the publisher attached to this runner.
        """

        if self.executor_config.subscriber is not None:
            self.publisher.subscribe(
                stream_subscriber(self.executor_config.subscriber),
                name="Streaming Subscriber",
            )

    def _close(self):
        """
        Closes the runner and cleans up all resources.

        - Shuts down the state object
        - Detaches logging handlers so they aren't duplicated
        - Deletes all the global variables that were registered in the context
        """
        # the publisher should have already been closed in `_run_base`
        self.rt_state.shutdown()

        if self._has_custom_logging:
            restore_module_logging()

        delete_globals()
        # by deleting all of the state variables we are ensuring that the next time we create a runner it is fresh

    @property
    def info(self) -> ExecutionInfo:
        """
        Returns the current state of the runner.

        This is useful for debugging and viewing the current state of the run.
        """
        return self.rt_state.info

    def payload(self) -> Dict[str, Any]:
        """
        Gets the complete json payload tied to this session.

        The outputted json schema is maintained in (link here)
        """
        info = self.info

        run_list = info.graph_serialization()

        full_dict = {
            "session_id": self._identifier,
            "session_name": self.name,
            "start_time": self._start_time,
            "end_time": time.time(),
            "runs": run_list,
        }

        return json.loads(json.dumps(full_dict))


@overload
def session(
    func: Callable[_P, Coroutine[Any, Any, _TOutput]],
) -> Callable[_P, Coroutine[Any, Any, Tuple[_TOutput, Session]]]:
    """
    Decorator for async functions without configuration (used as @session).

    This automatically creates and manages a Session context with default settings.
    The decorated function returns a tuple of (result, session).
    """
    ...


@overload
def session(
    func: None = None,
    *,
    name: str | None = None,
    context: Dict[str, Any] | None = None,
    timeout: float | None = None,
    end_on_error: bool | None = None,
    logging_setting: AllowableLogLevels | None = None,
    log_file: str | os.PathLike | None = None,
    broadcast_callback: (
        Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
    ) = None,
    prompt_injection: bool | None = None,
    save_state: bool | None = None,
) -> Callable[
    [Callable[_P, Coroutine[Any, Any, _TOutput]]],
    Callable[_P, Coroutine[Any, Any, Tuple[_TOutput, Session]]],
]:
    """
    Decorator for async functions with configuration (used as @session(...)).

    This automatically creates and manages a Session context with custom settings.
    The decorated function returns a tuple of (result, session).

    Note: Do not provide the 'func' parameter - it's handled automatically by Python.

    Args:
        name (str | None, optional): Optional name for the session. This name will be included in the saved state file if `save_state` is True.
        context (Dict[str, Any], optional): A dictionary of global context variables to be used during the execution.
        timeout (float, optional): The maximum number of seconds to wait for a response to your top-level request.
        end_on_error (bool, optional): If True, the execution will stop when an exception is encountered.
        logging_setting (AllowableLogLevels, optional): The setting for the level of logging you would like to have. This will override the module-level logging settings for the duration of this session.
        log_file (str | os.PathLike | None, optional): The file to which the logs will be written.
        broadcast_callback (Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None, optional): A callback function that will be called with the broadcast messages.
        prompt_injection (bool, optional): If True, the prompt will be automatically injected from context variables.
        save_state (bool, optional): If True, the state of the execution will be saved to a file at the end of the run in the `.railtracks` directory.

    Returns:
        A decorator function that takes an async function and returns a new async function
        that returns a tuple of (original_result, session).
    """
    ...


def session(
    func: Callable[_P, Coroutine[Any, Any, _TOutput]] | None = None,
    *,
    name: str | None = None,
    context: Dict[str, Any] | None = None,
    timeout: float | None = None,
    end_on_error: bool | None = None,
    logging_setting: AllowableLogLevels | None = None,
    log_file: str | os.PathLike | None = None,
    broadcast_callback: (
        Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
    ) = None,
    prompt_injection: bool | None = None,
    save_state: bool | None = None,
) -> (
    Callable[_P, Coroutine[Any, Any, Tuple[_TOutput, Session]]]
    | Callable[
        [Callable[_P, Coroutine[Any, Any, _TOutput]]],
        Callable[_P, Coroutine[Any, Any, Tuple[_TOutput, Session]]],
    ]
):
    """
    This decorator automatically creates and manages a Session context for the decorated function,
    allowing async functions to use Railtracks operations without manually managing the session lifecycle.

    Can be used as:
    - @session (without parentheses) - uses default settings
    - @session() (with empty parentheses) - uses default settings
    - @session(name="my_task", timeout=30) (with configuration parameters)

    When using this decorator, the function returns a tuple containing:
    1. The original function's return value
    2. The Session object used during execution

    This allows access to session information (like execution state, logs, etc.) after the function completes,
    while maintaining the simplicity of decorator usage.

    Args:
        name (str | None, optional): Optional name for the session. This name will be included in the saved state file if `save_state` is True.
        context (Dict[str, Any], optional): A dictionary of global context variables to be used during the execution.
        timeout (float, optional): The maximum number of seconds to wait for a response to your top-level request.
        end_on_error (bool, optional): If True, the execution will stop when an exception is encountered.
        logging_setting (AllowableLogLevels, optional): The setting for the level of logging you would like to have. This will override the module-level logging settings for the duration of this session.
        log_file (str | os.PathLike | None, optional): The file to which the logs will be written.
        broadcast_callback (Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None, optional): A callback function that will be called with the broadcast messages.
        prompt_injection (bool, optional): If True, the prompt will be automatically injected from context variables.
        save_state (bool, optional): If True, the state of the execution will be saved to a file at the end of the run in the `.railtracks` directory.

    Returns:
        When used as @session (without parentheses): Returns the decorated function that returns (result, session).
        When used as @session(...) (with parameters): Returns a decorator function that takes an async function
        and returns a new async function that returns (result, session).
    """

    def decorator(
        target_func: Callable[_P, Coroutine[Any, Any, _TOutput]],
    ) -> Callable[_P, Coroutine[Any, Any, Tuple[_TOutput, Session]]]:
        # Validate that the decorated function is async
        if not inspect.iscoroutinefunction(target_func):
            raise TypeError(
                f"@session decorator can only be applied to async functions. "
                f"Function '{target_func.__name__}' is not async. "
                f"Add 'async' keyword to your function definition."
            )

        @wraps(target_func)
        async def wrapper(
            *args: _P.args, **kwargs: _P.kwargs
        ) -> Tuple[_TOutput, Session]:
            session_obj = Session(
                context=context,
                timeout=timeout,
                end_on_error=end_on_error,
                logging_setting=logging_setting,
                log_file=log_file,
                broadcast_callback=broadcast_callback,
                name=name,
                prompt_injection=prompt_injection,
                save_state=save_state,
            )

            with session_obj:
                result = await target_func(*args, **kwargs)
                return result, session_obj

        return wrapper

    # If used as @session without parentheses
    if func is not None:
        return decorator(func)

    # If used as @session(...)
    return decorator
