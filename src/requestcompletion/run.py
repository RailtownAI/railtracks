import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, ParamSpec, TypeVar

from .config import ExecutorConfig
from .context.central import (
    delete_globals,
    get_global_config,
    register_globals,
)
from .execution.coordinator import Coordinator
from .execution.execution_strategy import AsyncioExecutionStrategy
from .info import (
    ExecutionInfo,
)
from .interaction.call import call
from .nodes.nodes import Node
from .pubsub.messages import (
    RequestCompletionMessage,
)
from .pubsub.publisher import RCPublisher
from .pubsub.subscriber import stream_subscriber
from .state.state import RCState
from .utils.logging.config import detach_logging_handlers, prepare_logger
from .utils.logging.create import get_rc_logger

logger = get_rc_logger("Runner")

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


class RunnerCreationError(Exception):
    """
    A basic exception to representing when a runner is created when one already exists.
    """

    pass


class RunnerNotFoundError(Exception):
    """
    A basic exception to representing when no runner can be found
    """

    pass


class Runner:
    """
    The main class used to run flows in the Request Completion framework.

    Example Usage:
    ```python
    import requestcompletion as rc

    with rc.Runner() as run:
        result = run.run_sync(RNGNode)
    ```
    """

    # singleton pattern
    _instance = None

    def __init__(
        self, executor_config: ExecutorConfig = None, context: Dict[str, Any] = None
    ):
        # first lets read from defaults if nessecary for the provided input config
        if executor_config is None:
            executor_config = get_global_config()

        self.executor_config = executor_config

        if context is None:
            context = {}

        # TODO see issue about logger
        prepare_logger(
            setting=executor_config.logging_setting,
            path=executor_config.log_file,
        )
        self.publisher: RCPublisher[RequestCompletionMessage] = RCPublisher()

        self._identifier = executor_config.run_identifier

        executor_info = ExecutionInfo.create_new()
        self.coordinator = Coordinator(
            execution_modes={"async": AsyncioExecutionStrategy()}
        )
        self.rc_state = RCState(
            executor_info, executor_config, self.coordinator, self.publisher
        )

        self.coordinator.start(self.publisher)
        self.setup_subscriber()
        register_globals(
            runner_id=self._identifier,
            rc_publisher=self.publisher,
            parent_id=None,
            executor_config=executor_config,
            global_context_vars=context,
        )

        logger.debug("Runner %s is initialized" % self._identifier)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.executor_config.save_state:
            try:
                covailence_dir = Path(".covailence")
                covailence_dir.mkdir(
                    exist_ok=True
                )  # Creates if doesn't exist, skips otherwise.

                file_path = (
                    covailence_dir / f"{self.executor_config.run_identifier}.json"
                )
                if file_path.exists():
                    logger.warning("File %s already exists, overwriting..." % file_path)

                logger.info("Saving execution info to %s" % file_path)

                file_path.write_text(self.info.graph_serialization())
            except Exception as e:
                logger.error(
                    "Error while saving to execution info to file",
                    exc_info=e,
                )

        self._close()

    def setup_subscriber(self):
        """
        Prepares and attaches the saved subscriber to the publisher attached to this runner.
        """

        if self.executor_config.subscriber is not None:
            self.publisher.subscribe(
                stream_subscriber(self.executor_config.subscriber),
                name="Streaming Subscriber",
            )

    # @warnings.deprecated("run_sync is deprecated, use `rc.call_sync`")
    def run_sync(
        self,
        start_node: Callable[_P, Node] | None = None,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ):
        """Runs the provided node synchronously."""
        asyncio.run(call(start_node, *args, **kwargs))

        return self.rc_state.info

    def _close(self):
        # the publisher should have already been closed in `_run_base`
        self.rc_state.shutdown()
        detach_logging_handlers()
        delete_globals()
        # by deleting all of the state variables we are ensuring that the next time we create a runner it is fresh

    @property
    def info(self) -> ExecutionInfo:
        """
        Returns the current state of the runner.

        This is useful for debugging and viewing the current state of the run.
        """
        return self.rc_state.info

    async def call(
        self,
        node: Callable[_P, Node[_TOutput]],
        /,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ):
        return await call(node, *args, **kwargs)

    # @warnings.deprecated("run_sync is deprecated, use `rc.call_sync`")
    async def run(
        self,
        start_node: Callable[_P, Node] | None = None,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ):
        """Runs the rc framework with the given start node and provided arguments."""

        await self.call(start_node, *args, **kwargs)

        return self.rc_state.info

    async def cancel(self, node_id: str):
        raise NotImplementedError(
            "Currently we do not support cancelling nodes. Please contact Logan to add this feature."
        )
        # collects the parent id of the current node that is running that is gonna get cancelled
        await self.rc_state.cancel(node_id)

    # TODO implement this method and any additional logic in rc_state that is required.
    def from_state(self, executor_info: ExecutionInfo):
        raise NotImplementedError(
            "Currently we do not support running from a state object. Please contact Logan to add this feature."
        )
        # self.rc_state = RCState(executor_info)
