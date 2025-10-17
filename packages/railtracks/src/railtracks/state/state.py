from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Dict, List, ParamSpec, Tuple, TypeVar

from ..context.central import update_parent_id
from ..execution.coordinator import Coordinator
from ..execution.task import Task
from ..pubsub.messages import (
    FatalFailure,
    RequestCompletionMessage,
    RequestCreation,
    RequestCreationFailure,
    RequestFailure,
    RequestFinishedBase,
    RequestSuccess,
)
from ..pubsub.publisher import RTPublisher
from ..utils.logging.action import (
    RequestCreationAction,
    RequestFailureAction,
    RequestSuccessAction,
)

# all the things we need to import from RT directly.
# all the things we need to import from RT directly.
from .request import Cancelled, Failure
from .utils import create_sub_state_info

if TYPE_CHECKING:
    from railtracks.utils.config import ExecutorConfig

from railtracks.exceptions import FatalError, NodeInvocationError
from railtracks.nodes.nodes import Node
from railtracks.utils.logging.create import get_rt_logger
from railtracks.utils.profiling import Stamp

from .info import ExecutionInfo

_TOutput = TypeVar("_TOutput")
_P = ParamSpec("_P")


class RTState:
    """
    RTState is an internal RT object used to manage state of the request completion system. This object has a couple of
    major functions:
    1. It allows you to create a new state object every time you want to run the system.
    2. The state object will connect to the provided publisher and will handle all the messages that are sent to it.
    2. It allows you to invoke the graph at a given node and will handle the execution of the graph.
    3. It will handle all the exceptions that are thrown during the execution of the graph.
    4. It will handle the creation of new requests and the management of the state of the nodes.
    5. It will save all the details in the object so that you can access them later.
    6. Simple logging of action completed in the system.

    The object is designed to be a large state object that contains all important details about the running of the
    system during execution. It can be accessed after run, to collect important details that will aid debugging and
    allow for retrospective analysis of the system.
    """

    def __init__(
        self,
        execution_info: ExecutionInfo,
        executor_config: ExecutorConfig,
        coordinator: Coordinator,
        publisher: RTPublisher,
    ):
        self._node_heap = execution_info.node_forest
        self._request_heap = execution_info.request_forest
        self._stamper = execution_info.stamper

        self.executor_config = executor_config
        self.rc_coordinator = coordinator

        # each new instance of a state object should have its own logger.
        self.logger = get_rt_logger()

        publisher.subscribe(self.handle, "State Object Handler")
        self.publisher = publisher

    async def handle(self, item: RequestCompletionMessage) -> None:
        """
        A simpler handler function designed to handle the messages from the publisher object by the state object.

        Args:
            item: The item that was sent to the publisher. It can be any of the RequestCompletionMessage types.
        """
        # TODO: fix up these abstractions so it consistent that we are mapping the request type into its proper type.
        if isinstance(item, RequestFinishedBase):
            await self.handle_result(item)
        if isinstance(item, RequestCreation):
            if item.current_node_id is not None:
                update_parent_id(item.current_node_id, item.current_run_id)

            assert item.new_request_id not in self._request_heap.heap().keys()

            await self.call_nodes(
                parent_node_id=item.current_node_id,
                request_id=item.new_request_id,
                node=item.new_node_type,
                args=item.args,
                kwargs=item.kwargs,
            )

    def shutdown(self):
        """
        Shutdown the state object and all of its references.
        """
        self.rc_coordinator.shutdown()

    @property
    def is_empty(self):
        """
        Determines if the state object is currently empty (i.e. no nodes or requests are present).
        """
        return len(self._node_heap.heap()) == 0 and len(self._request_heap.heap()) == 0

    def add_stamp(self, message: str):
        """
        Manually adds a stamp with the provided message to the stamp generator

        Args:
            message: The message you would like to attach to the stamp

        """
        self._stamper.create_stamp(message)

    async def cancel(self, node_id: str):
        """
        Cancels the running process of the node with the given identifier.

        It will update the state, but it will not kill the process running the node.
        """
        if node_id not in self._node_heap.heap():
            assert False

        r_id = self._request_heap.get_request_from_child_id(node_id)
        self._request_heap.update(
            r_id, Cancelled, self._stamper.create_stamp(f"Cancelled request {r_id}")
        )

    def _create_node_and_request(
        self,
        *,
        parent_node_id: str,
        request_id: str | None,
        node: Callable[_P, Node],
        args: _P.args,
        kwargs: _P.kwargs,
    ) -> str:
        """
        Creates a node using the creator function (node).

        ASIDE: This function is the only way you should create nodes in the system. If you create them elsehwere they
        will not be tracked in the system.


        Args:
            parent_node_id: The parent node id of the node you are creating (used for tracking of requests)
            node: The Node you would like to create
            args: The arguments to pass to the node
            kwargs: The keyword arguments to pass to the node

        Returns:
            The request id of the request created between parent and child.
        """

        # 1. Create the node here
        node = node(*args, **kwargs)

        # 2. Add it to the node heap.
        sc = self._stamper.stamp_creator()
        parent_node_type = self._node_heap.get_node_type(parent_node_id)
        parent_node_name = parent_node_type.name() if parent_node_type else "START"

        request_creation_obj = RequestCreationAction(
            parent_node_name=parent_node_name,
            child_node_name=node.name(),
            input_args=args,
            input_kwargs=kwargs,
        )

        stamp = sc(request_creation_obj.to_logging_msg())

        self._node_heap.update(node, stamp)

        # 3. Attach the requests that will tied to this node.
        request_ids = self._create_new_request_set(
            parent_node=parent_node_id,
            children=[node.uuid],
            input_args=[args],
            input_kwargs=[kwargs],
            stamp=stamp,
            request_ids=[request_id],
        )

        self.logger.info(request_creation_obj.to_logging_msg())
        # 4. Return the request id of the node that was created.
        return request_ids[0]

    async def call_nodes(
        self,
        *,
        parent_node_id: str | None,
        request_id: str | None,
        node: Callable[_P, Node[_TOutput]],
        args: _P.args,
        kwargs: _P.kwargs,
    ):
        """
        This function will handle the creation of the node and the subsequent running of the node returning the result.

        Important: If an exception was thrown during the execution of the request, it will pass through this function,
        and will be raised.

        Args:
            parent_node_id: The parent node id of the node you are calling. None if it has no parent.
            request_id: The request id of the request you are creating. If None, a new request id will be created.
            node: The node you would like to create.
            args: The arguments to pass to the node.
            kwargs: The keyword arguments to pass to the node.

        Returns:
            The output of the node that was run. It will match the output type of the child node that was run.

        """
        try:
            request_id = self._create_node_and_request(
                parent_node_id=parent_node_id,
                request_id=request_id,
                node=node,
                args=args,
                kwargs=kwargs,
            )
        except Exception as e:
            # TODO improve this so we know the name of the node trying to be created in the case of a tool call llm.
            rfa = RequestFailureAction(
                node_name=node.name() if hasattr(node, "name") else "Unknown",
                exception=e,
            )
            await self.publisher.publish(
                RequestCreationFailure(
                    request_id=request_id,
                    error=e,
                )
            )
            self.logger.exception(rfa.to_logging_msg())
            raise e
        # you have to run this in a task so it isn't blocking other completions
        outputs = asyncio.create_task(self._run_request(request_id))

        return outputs

    # TODO handle the business around parent node with automatic checkpointing.
    def _create_new_request_set(
        self,
        parent_node: str | None,
        children: List[str],
        input_args: List[Tuple],
        input_kwargs: List[Dict[str, Tuple]],
        stamp: Stamp,
        request_ids: List[str | None] | None = None,
    ) -> List[str]:
        """
        Creates a new set of requests from the provided details. Essentially we will be creating a new request from the
        parent node to each of the children nodes. They will all share the stamp and will have a descriptive message
        attached to each of them.

        Note that you are supposed to provide a list of items. It is assumed that all the lists are the same length.
        Each index in the lists corresponds to the same child node.

        Args:
            parent_node: The identifier of the parent node which is calling the children. If none is provided we assume there is no parent.
            children: The list of node_ids that you would like to call.
            input_args: The list of arguments to pass to each of the children nodes.
            input_kwargs: The list of keyword arguments to pass to each of the children nodes.
            request_ids: The list of request ids to use for each of the children nodes. I
            stamp: The stamp you would like to attach to each of the requests.
        """

        # note it is assumed that all of the children id are valid and have already been created.
        assert all(n in self._node_heap for n in children), (
            "You cannot add a request for a node which has not yet been added"
        )

        if request_ids is None:
            request_ids = [None] * len(children)

        # to simplify we are going to create a new request for each child node with the parent as its source.
        request_ids = list(
            map(
                self._request_heap.create,
                request_ids,
                [parent_node] * len(children),
                children,
                input_args,
                input_kwargs,
                [stamp for _ in children],
            )
        )

        return request_ids

    async def _run_request(self, request_id: str):
        """
        Runs the request for the given request id.

        1. It will use the request to collect the identifier of the child node and then run the node.
        2. It will submit the task to the coordinator to run the node.
        3. It will return once the request has been placed.


        Args:
            request_id: The identifier for the request you would like to run


        """
        child_node_id = self._request_heap[request_id].sink_id
        node = self._node_heap[child_node_id].node
        return await self.rc_coordinator.submit(
            task=Task(request_id=request_id, node=node),
            mode="async",
        )

    async def _handle_failed_request(
        self, failed_node_name: str, request_id: str, exception: Exception
    ):
        """
        Handles the provided exception for the given request identifier. It will publish a message to the publisher if
        deemed necessary and will return a Failure object containing the exception.

        This function will handle the following tasks:
        1. logs the exception
        2. Determines if the error is fatal and whether it should kill the system. If so it will publish a FatalFailure
            message to the publisher
        3. Returns a Failure object.

        Args:
            failed_node_name: The name of the node that failed. This is used for logging and debugging.
            request_id: The request in which this error occurred
            exception: The exception thrown during this request.

        Returns:
            An object containing the error thrown during the request wrapped in a Failure object.
        """
        # before doing any handling we must make sure our exception history object is up to date.

        node_exception_action = RequestFailureAction(
            node_name=failed_node_name,
            exception=exception,
        )

        if self.executor_config.end_on_error:
            self.logger.critical(
                node_exception_action.to_logging_msg(), exc_info=exception
            )
            await self.publisher.publish(FatalFailure(error=exception))
            return Failure(exception)

        # fatal exceptions should only be thrown if there is something seriously wrong. At the moment only NodeInvocatioErrors have 'fatal' flags
        if (
            isinstance(exception, NodeInvocationError) and exception.fatal
        ) or isinstance(exception, FatalError):
            self.logger.critical(
                node_exception_action.to_logging_msg(), exc_info=exception
            )
            await self.publisher.publish(FatalFailure(error=exception))
            return Failure(exception)

        # for any other error we want it to bubble up so the user can handle.
        self.logger.error(node_exception_action.to_logging_msg(), exc_info=exception)
        return Failure(exception)

    @property
    def info(self):
        """Returns the current state as an ExecutionInfo object."""
        return ExecutionInfo(
            self._request_heap,
            self._node_heap,
            self._stamper,
        )

    def get_info(self, ids: List[str] | str) -> ExecutionInfo:
        """
        Gets the info object for the current state but filtered to include on the children of the provided ids.

        You should provide minimal ids to this function (i.e. you should not provide the list of children instead just
        the parent node id). If you provide a parent and its children behavior is undefined.
        """
        filtered_nodes, filtered_requests = create_sub_state_info(
            self._node_heap.heap(), self._request_heap.heap(), ids
        )
        # TODO: deal with the weirdness around double representation in the stamper.
        #  specifically we need to make sure that the data in the stamper is only for the subset and not for the global state.
        return ExecutionInfo(
            node_forest=filtered_nodes,
            request_forest=filtered_requests,
            stamper=self._stamper,
        )

    async def _handle_successful_request(
        self,
        node_name: str,
        result: Any,
    ):
        """
        Handles the successful completion of a request. It will log the success and return the result.
        """
        request_completion_obj = RequestSuccessAction(
            node_name=node_name,
            output=result,
        )

        self.logger.info(request_completion_obj.to_logging_msg())
        return result

    async def handle_result(self, result: RequestFinishedBase):
        """
        Handles the given request completion.

        If it is a Failure it will log and post any relevant items to the publisher and return the error.

        This function will also handle successful requests in the same way.

        Raises:
            TypeError: If the provided result does not match any of the expected types.
        """
        if isinstance(result, RequestFailure):
            # if the node state is None, it means the node was never created so we don't need to handle it
            output = await self._handle_failed_request(
                result.node.name(), result.request_id, result.error
            )
            returnable_result = result.error

        elif isinstance(result, RequestSuccess):
            output = await self._handle_successful_request(
                node_name=result.node.name(),
                result=result.result,
            )
            returnable_result = result.result

        elif isinstance(result, RequestCreationFailure):
            # we do not need to both handling this.
            return
        else:
            raise TypeError(f"Unknown result type: {type(result)}")

        stamp = self._stamper.create_stamp(f"Finished executing {result.node.name()}")

        self._request_heap.update(result.request_id, output, stamp)
        self._node_heap.update(result.node, stamp)

        return returnable_result
