from __future__ import annotations

import asyncio
import uuid
from collections import deque


from typing import TypeVar, List, Callable, ParamSpec, Tuple, Dict, TYPE_CHECKING

# all the things we need to import from RC directly.
from .request import Cancelled, Failure
from ..utils.logging.action import (
    RequestCreationAction,
    RequestCompletionAction,
    NodeExceptionAction,
)

if TYPE_CHECKING:
    from .. import ExecutorConfig
from ..context import parent_id
from ..exceptions import FatalError
from ..nodes.nodes import Node
from ..info import ExecutionInfo
from ..exceptions import ExecutionError, GlobalTimeOutError
from ..utils.profiling import Stamp
from ..utils.logging.create import get_rc_logger


_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")

LOGGER_NAME = "RUNNER"


class RCState:
    """
    RCState is an internal RC object used to manage state of the request completion system. This object has a couple of
    major functions:
    1. It allows you to create a new state object every time you want to run the system.
    2. It allows you to invoke the graph at a given node and will handle the execution of the graph.
    3. It will handle all the exceptions that are thrown during the execution of the graph.
    4. It will handle the creation of new requests and the management of the state of the nodes.
    5. It will save all the details in the object so that you can access them later.
    6. Simple logging of action completed in the system.

    The object is designed to be a large state object that contains all important details about the running of the
    system during execution. It can be accessed after run, to collect important details that will aid debugging and
    allow for retrospective analysis of the system.
    """

    # the main role of this object is to augment the executor object with all the things it needs to track state as the
    #  the graph runs.
    def __init__(self, execution_info: ExecutionInfo, executor_config: ExecutorConfig):
        self._node_heap = execution_info.node_heap
        self._request_heap = execution_info.request_heap
        self._stamper = execution_info.stamper

        self.exception_history = deque[Exception](execution_info.exception_history)

        self.executor_config = executor_config

        ## These are the elements which need to be created as new objects every time. They should not serialized.

        # each new instance of a state object should have its own logger.
        self.logger = get_rc_logger(LOGGER_NAME)

    @property
    def is_empty(self):
        return len(self._node_heap.heap()) == 0 and len(self._request_heap.heap()) == 0

    def add_stamp(self, message: str):
        """
        Manually adds a stamp with the provided message to the stamp generator

        Args:
            message: The message you would like to attach to the stamp

        Returns:
            None
        """
        self._stamper.create_stamp(message)

    async def execute(self, request_id: str):
        """Executes the graph starting at the provided request id."""
        # TODO: come up with a better algorithm for finding the start of execution.

        try:
            _ = await asyncio.wait_for(
                self._run_request(request_id), timeout=self.executor_config.timeout
            )
            # Note that since this is the insertion requests, its output is our answer.

        except asyncio.TimeoutError:
            raise ExecutionError(
                failed_request=self._request_heap["START"],
                execution_info=self.info,
                final_exception=GlobalTimeOutError(self.executor_config.timeout),
            )

    async def cancel(self, node_id: str):
        if node_id not in self._node_heap.heap():
            assert False

        r_id = self._request_heap.get_request_from_child_id(node_id)
        self._request_heap.update(
            r_id, Cancelled, self._stamper.create_stamp(f"Cancelled request {r_id}")
        )

    async def _run_node(
        self,
        node: Node,
    ):
        """Runs the provided node and returns the output of the node."""

        return await node.invoke()

    def _create_node_and_request(
        self,
        parent_node_id: str,
        node: Callable[_P, Node],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> str:
        """
        Creates a node using the creator and then registers it with the registry. This will allow the register method to
        act on the node.

        Note this is the only way you can add node to the system.

        Side Effects:
        It will set the parent_id context manager variable to the new node id.

        Args:
            parent_node_id: The parent node id of the node you are creating (used for tracking of requests)
            node: The Node you would like to create
            *args: The arguments to pass to the node
            **kwargs: The keyword arguments to pass to the node

        Returns:
            The request id of the request created between parent and child.
        """

        # 1. Create the node here
        node = node(*args, **kwargs)

        # This is a critical registration step so other elements are away that we have officially created the node.
        parent_id.set(node.uuid)

        # 2. Add it to the node heap.
        sc = self._stamper.stamp_creator()
        self._node_heap.update(node, sc(f"Creating {node.pretty_name()}"))

        # 3. Attach the requests that will tied to this node.
        request_ids = self._create_new_request_set(
            parent_node_id, [node.uuid], [args], [kwargs], sc
        )

        parent_node_type = self._node_heap.get_node_type(parent_node_id)
        parent_node_name = (
            parent_node_type.pretty_name() if parent_node_type else "START"
        )
        request_creation_obj = RequestCreationAction(
            parent_node_name=parent_node_name,
            child_node_name=node.pretty_name(),
            input_args=args,
            input_kwargs=kwargs,
        )

        self.logger.info(request_creation_obj.to_logging_msg())
        # 4. Return the request id of the node that was created.
        return request_ids[0]

    async def call_nodes(
        self,
        parent_node_id: str | None,
        node: Callable[_P, Node[_TOutput]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _TOutput:
        """
        This function will handle the creation of the node and the subsequent running of the node returning the result.

        Important: If an exception was thrown during the execution of the request, it will pass through this function,
        and will be raised.

        Args:
            parent_node_id: The parent node id of the node you are calling. None if it has no parent.
            node: The node you would like to call.

        Returns:
            The output of the node that was run. It will match the output type of the child node that was run.

        """
        request_id = self._create_node_and_request(
            parent_node_id, node, *args, **kwargs
        )

        outputs: _TOutput = await self._run_request(request_id)
        return outputs

    # TODO handle the business around parent node with automatic checkpointing.
    def _create_new_request_set(
        self,
        parent_node: str | None,
        children: List[str],
        input_args: List[Tuple],
        input_kwargs: List[Dict[str, Tuple]],
        stamp_gen: Callable[[str], Stamp],
    ) -> List[str]:
        """
        Creates a new set of requests from the provided details. Essentially we will be creating a new request from the
        parent node to each of the children nodes. They will all share the stamp and will have a descriptive message
        attached to each of them

        Note that all the identifiers for the

        Args:
            parent_node: The identifier of the parent node which is calling the children. If none is provided we assume there is no parent.
            children: The list of node_ids that you would like to call.
            stamp_gen: A function that will create a new stamp of the same number.
        """

        # note it is assumed that all of the children id are valid and have already been created.
        assert all(
            n in self._node_heap for n in children
        ), "You cannot add a request for a node which has not yet been added"
        parent_node_name = (
            self._node_heap.id_type_mapping[parent_node]
            if parent_node is not None
            else "START"
        )
        # to simplify we are going to create a new request for each child node with the parent as its source.
        request_ids = list(
            map(
                self._request_heap.create,
                [str(uuid.uuid4()) if parent_node else "START" for _ in children],
                [parent_node] * len(children),
                children,
                input_args,
                input_kwargs,
                [
                    stamp_gen(
                        f"Adding request between {parent_node_name} and {self._node_heap.id_type_mapping[n]}"
                    )
                    for n in children
                ],
            )
        )

        return request_ids

    async def _run_request(self, request_id: str):
        """
        Runs the request for the given request id.

        1. It will use the request to collect the identifier of the child node and then run the node.
        2. It will then handle any errors thrown during execution.
        3. It will save the new state to the state objects
        4. It will return the result of the request. (or if any error was raised during execution it will throw the error)

        Important: If an exception was thrown during the execution of the request, it will be be raised here.

        Args:
            request_id: The request you would like to run

        Returns:
            The result of the request. It will match the output type of the child node that was run.

        """
        child_node_id = self._request_heap[request_id].sink_id
        node = self._node_heap[child_node_id].node
        try:
            result = await self._run_node(node)
        except Exception as e:
            handled_error = self._handle_failed_request(
                node.pretty_name(), request_id, e
            )
            result = handled_error

        stamp = self._stamper.create_stamp(f"Finished executing {node.pretty_name()}")
        request_completion_obj = RequestCompletionAction(
            child_node_name=node.pretty_name(),
            output=result,
        )

        self.logger.info(request_completion_obj.to_logging_msg())

        self._request_heap.update(request_id, result, stamp)
        self._node_heap.update(node, stamp)

        if isinstance(result, Failure):
            raise result.exception

        return result

    def _handle_failed_request(
        self, failed_node_name: str, request_id: str, exception: Exception
    ):
        """
        Handles the provided exception for the given request identifier.

        If the given exception is a `FatalException` or if the config flag for `end_on_error` is set to be true, then
        the function will return a `ExecutionError` object wrapped in a `Failure` object.

        Otherwise, it will return a `Failure` object containing the exception that was thrown.

        Args:
            request_id: The request in which this error occurred
            exception: The exception thrown during this request.

        Returns:
            An object containing the error thrown during the request wrapped in a Failure object.

        Raises:
            ExecutionError: If the exception was a `FatalException`, or if the config flag for `end_on_error` is set
            to be true.

        """
        # before doing any handling we must make sure our exception history object is up to date.
        self.exception_history.append(exception)
        node_exception_action = NodeExceptionAction(
            node_name=failed_node_name,
            exception=exception,
        )

        if self.executor_config.end_on_error:
            self.logger.critical(node_exception_action.to_logging_msg())
            ee = ExecutionError(
                failed_request=self._request_heap[request_id],
                execution_info=self.info,
                final_exception=exception,
            )
            return Failure(ee)

        # fatal exceptions should only be thrown if there is something seriously wrong.
        if isinstance(exception, FatalError):
            self.logger.critical(node_exception_action.to_logging_msg())
            ee = ExecutionError(
                failed_request=self._request_heap[request_id],
                execution_info=self.info,
                final_exception=exception,
            )
            return Failure(ee)

        # for any other error we want it to bubble up so the user can handle.
        self.logger.exception(node_exception_action.to_logging_msg())
        return Failure(exception)

    @property
    def info(self):
        """Returns the current state as an ExecutionInfo object."""
        return ExecutionInfo(
            node_heap=self._node_heap,
            request_heap=self._request_heap,
            stamper=self._stamper,
            exception_history=list(self.exception_history),
        )
