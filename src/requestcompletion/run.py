import asyncio
import threading
import warnings
from typing import TypeVar, ParamSpec, Callable

from .config import ExecutorConfig
from .utils.stream import DataStream, Subscriber
from .nodes.nodes import Node
from .utils.logging.config import prepare_logger, delete_loggers


from .info import (
    ExecutionInfo,
)
from .state.execute import RCState

from .context import active_runner, streamer, config, parent_id

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
        self,
        subscriber: Callable[[str], None] = None,
        executor_config: ExecutorConfig = None,
    ):
        # first lets read from defaults if nessecary for the provided input config
        if executor_config is None:
            saved_config = config.get()
            if saved_config is None:
                executor_config = ExecutorConfig()
            else:
                executor_config = saved_config

        if subscriber is None:
            saved_subscriber = streamer.get()
            if saved_subscriber is None:
                subscriber = None
            else:
                subscriber = saved_subscriber

        # TODO see issue about logger
        prepare_logger(
            setting=executor_config.logging_setting,
        )

        executor_info = ExecutionInfo.create_new()

        self.rc_state = RCState(executor_info, executor_config)

        if subscriber is None:
            self._data_streamer = DataStream()
        else:

            class DynamicSubscriber(Subscriber[str]):
                def handle(self, item: str) -> None:
                    subscriber(item)

            self._data_streamer = DataStream(subscribers=[DynamicSubscriber()])

    def __enter__(self):
        # if active_runner.get() is not None:
        #     raise RunnerCreationError(
        #         "A runner already exists, you cannot create nested Runners. Replace this runner with the simpler `rc.call` to call the node."
        #     )
        active_runner.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close()

    def run_sync(
        self,
        start_node: Callable[_P, Node] | None = None,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ):
        """Runs the provided node synchronously."""
        # If no loop is running, create one and run the coroutine.
        result = asyncio.run(self.run(start_node, *args, **kwargs))
        return result

    def _close(self):
        threading.Thread(
            self._data_streamer.stop(self.rc_state.executor_config.force_close_streams)
        ).start()

        delete_loggers()
        # by deleting all of the state variables we are ensuring that the next time we create a runner it is fresh
        active_runner.set(None)
        parent_id.set(None)

    @property
    def info(self) -> ExecutionInfo:
        """
        Returns the current state of the runner.

        This is useful for debugging and viewing the current state of the run.
        """
        return self.rc_state.info

    async def run(
        self,
        start_node: Callable[_P, Node] | None = None,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ):
        """Runs the rc framework with the given start node and provided arguments."""

        # relevant if we ever want to have future support for optional start nodes
        if not self.rc_state.is_empty:
            raise RuntimeError(
                "The run function can only be used to start not in the middle of a run."
            )

        await self.call(None, start_node, *args, **kwargs)

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

    async def call(
        self,
        parent_node_id: str | None,
        node: Callable[_P, Node[_TOutput]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ):
        # TODO refactor this to handle keyword arugments
        """
        An internal method used to call a node using the state object tied to this runner.

        The method will create a coroutine that you can interact with in whatever way using the `asyncio` framework.

        Args:
            parent_node_id: The parent node id of the node you are calling.
            node: The node you would like to calling.
        """
        return await self.rc_state.call_nodes(parent_node_id, node, *args, **kwargs)

    # TODO add support for any general user defined streaming object
    def stream(self, item: str):
        """
        Streams the provided message using the data streamer tied to this runner.

        Args:
            item: The message you would like to stream.

        """
        self._data_streamer.publish(item)


def get_runner() -> Runner | None:
    """
    Collects the current instance of the runner. If none exists it will return none.
    """

    curr_runner = active_runner.get()
    if curr_runner is None:
        return None
    return curr_runner


def set_config(executor_config: ExecutorConfig):
    """
    Sets the executor config for the current runner.
    """
    if get_runner() is not None:
        warnings.warn(
            "The executor config is being set after the runner has been created, changes will not be propagated to the current runner"
        )

    config.set(executor_config)


def set_streamer(subscriber: Callable[[str], None]):
    """
    Sets the data streamer for the current runner.
    """
    if get_runner() is not None:
        warnings.warn(
            "The data streamer is being set after the runner has been created, changes will not be propagated to the current runner"
        )

    streamer.set(subscriber)
