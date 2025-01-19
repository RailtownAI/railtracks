from typing import TypeVar, Any
import warnings

from ..nodes.nodes import Node

from ..context import (
    BaseContext,
    EmptyContext,
)

from .info import (
    ExecutionInfo,
)
from .config import ExecutorConfig
from .state.execute import RCState
from .tools.stream import Subscriber

_TOutput = TypeVar("_TOutput")
_TContext = TypeVar("_TContext", bound=BaseContext)


# TODO make the subscriber a lambda function input
def run(
    start_node: Node,
    context: _TContext = EmptyContext(),
    subscriber: Subscriber[str] = Subscriber.null_concrete_sub()(),
    executor_config: ExecutorConfig = ExecutorConfig(),
):
    if not isinstance(context, EmptyContext):
        warnings.warn("We do not support the injection of context at this time. We will use empty context")
        context = EmptyContext()

    return execute(
        start_node,
        ExecutionInfo.create_new(start_node, context, subscriber, executor_config),
    )


def execute(start_node: Node, executor_info: ExecutionInfo) -> ExecutionInfo:
    """
    Runs the given node handling any calls to other nodes eventually returning the finished result.

    Args:
        start_node: The node you would like to start from.
        executor_info: The configuration object that will be used to define the graph.

    Returns:
        A completed execution object which can generate on demand any details you would like to collect about the run.

    """

    return _unsafe_run(start_node, executor_info)


def _unsafe_run(
    start_node: Node,
    executor_info: ExecutionInfo,
):
    state = RCState(
        execution_info=executor_info,
    )

    state.invoke(start_node)

    # note the state object is pass by reference so this works well.
    return state.info


# TODO: Implement a "Type safe" run where the user provides a graph of allowable connections
#  ideally we have a way to do compile time as well as run-time checks on the outputs.


def safe_run(
    start_node: Node,
    graph: Any,  # TODO fill out this type
    context: _TContext,
    subscriber: Subscriber[str] = Subscriber.null_concrete_sub()(),
) -> ExecutionInfo:
    raise NotImplementedError("This function is not yet implemented")


class AlreadyRunningException(Exception):
    pass
