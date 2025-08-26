import os
import uuid
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, ParamSpec, TypeVar

from .context.central import (
    delete_globals,
    get_global_config,
    register_globals,
)
from .execution.coordinator import Coordinator
from .execution.execution_strategy import AsyncioExecutionStrategy
from .pubsub import RTPublisher, stream_subscriber
from .pubsub.messages import (
    RequestCompletionMessage,
)
from .state.info import (
    ExecutionInfo,
)
from .state.state import RTState
from .utils.config import ExecutorConfig
from .utils.logging.config import (
    allowable_log_levels,
    detach_logging_handlers,
    prepare_logger,
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
    - `timeout`: 150.0 seconds
    - `end_on_error`: False
    - `logging_setting`: "REGULAR"
    - `log_file`: None (logs will not be written to a file)
    - `broadcast_callback`: None (no callback for broadcast messages)
    - `run_identifier`: None (a random identifier will be generated)
    - `prompt_injection`: True (the prompt will be automatically injected from context variables)
    - `save_state`: True (the state of the execution will be saved to a file at the end of the run in the `.railtracks` directory)


    Args:
        context (Dict[str, Any], optional): A dictionary of global context variables to be used during the execution.
        timeout (float, optional): The maximum number of seconds to wait for a response to your top-level request.
        end_on_error (bool, optional): If True, the execution will stop when an exception is encountered.
        logging_setting (allowable_log_levels, optional): The setting for the level of logging you would like to have.
        log_file (str | os.PathLike | None, optional): The file to which the logs will be written.
        broadcast_callback (Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None, optional): A callback function that will be called with the broadcast messages.
        identifier (str | None, optional): A unique identifier for the run. If none one will be generated automatically.
        prompt_injection (bool, optional): If True, the prompt will be automatically injected from context variables.
        save_state (bool, optional): If True, the state of the execution will be saved to a file at the end of the run in the `.railtracks` directory.

    Example Usage:
    ```python
    import railtracks as rt

    with rt.Session() as run:
        result = await rt.call(rt.nodes.NodeA, "Hello World")
    ```
    """

    def __init__(
        self,
        context: Dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
        end_on_error: bool | None = None,
        logging_setting: allowable_log_levels | None = None,
        log_file: str | os.PathLike | None = None,
        broadcast_callback: (
            Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None
        ) = None,
        identifier: str = None,
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

        if identifier is None:
            identifier = str(uuid.uuid4())

        prepare_logger(
            setting=self.executor_config.logging_setting,
            path=self.executor_config.log_file,
        )
        self.publisher: RTPublisher[RequestCompletionMessage] = RTPublisher()

        self._identifier = identifier

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
            runner_id=self._identifier,
            rt_publisher=self.publisher,
            parent_id=None,
            executor_config=self.executor_config,
            global_context_vars=context,
        )

        logger.debug("Session %s is initialized" % self._identifier)

    @classmethod
    def global_config_precedence(
        cls,
        timeout: float | None,
        end_on_error: bool | None,
        logging_setting: allowable_log_levels | None,
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

                file_path = railtracks_dir / f"{self._identifier}.json"
                if file_path.exists():
                    logger.warning("File %s already exists, overwriting..." % file_path)

                logger.info("Saving execution info to %s" % file_path)

                file_path.write_text(self.payload())
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
        detach_logging_handlers()
        delete_globals()
        # by deleting all of the state variables we are ensuring that the next time we create a runner it is fresh

    @property
    def info(self) -> ExecutionInfo:
        """
        Returns the current state of the runner.

        This is useful for debugging and viewing the current state of the run.
        """
        return self.rt_state.info

    def payload(self):
        """
        Gets the complete json payload tied to this session.

        The outputted json schema is maintained in (link here)
        """
        info = self.info

        return info.graph_serialization(self._identifier)
