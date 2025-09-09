from __future__ import annotations

from abc import ABC
from typing import Any, Literal, ParamSpec, Type, TypeVar

from railtracks.nodes.nodes import Node, NodeState

# RT specific imports

ExecutionConfigurations = Literal["async"]

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")
_TNode = TypeVar("_TNode", bound=Node)

############### Request Completion Messages ###############


class RequestCompletionMessage(ABC):
    """
    The base class for all messages on the request completion system.
    """

    def log_message(self) -> str:
        """Converts the message to a string ready to be logged."""
        return repr(self)


### Request Finished Messages ########
# TODO add generic typing for all these types


class RequestFinishedBase(RequestCompletionMessage, ABC):
    """
    A simple base class for all messages that pertain to a request finishing.
    """

    def __init__(
        self,
        *,
        request_id: str,
        node_state: NodeState[Node[_TOutput]] | None,
    ):
        self.request_id = request_id
        self.node_state = node_state

    @property
    def node(self) -> Node[_TOutput] | None:
        """
        Gets a node instance from the provided node state.

        Note: this function uses the functionality of `NodeState.instantiate()`
        """
        if self.node_state is None:
            return None

        return self.node_state.instantiate()

    def __repr__(self):
        return f"{self.__class__.__name__}(request_id={self.request_id}, node_state={self.node_state})"


class RequestSuccess(RequestFinishedBase):
    """
    A message that indicates the succseful completion of a request.
    """

    def __init__(
        self,
        *,
        request_id: str,
        node_state: NodeState[_TNode[_TOutput]],
        result: _TOutput,
    ):
        super().__init__(request_id=request_id, node_state=node_state)
        self.result = result

    def __repr__(self):
        return f"{self.__class__.__name__}(request_id={self.request_id}, node_state={self.node_state}, result={self.result})"

    def log_message(self) -> str:
        return f"{self.node_state.node.name()} DONE with result {self.result}"


class RequestFailure(RequestFinishedBase):
    """
    A message that indicates a failure in the request execution.
    """

    def __init__(
        self,
        *,
        request_id: str,
        node_state: NodeState[_TNode[_TOutput]] | None,
        error: Exception,
    ):
        super().__init__(request_id=request_id, node_state=node_state)
        self.error = error

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(request_id={self.request_id}, "
            f"node_state={self.node_state}, error={self.error})"
        )

    def log_message(self) -> str:
        return f"{self.node_state.node.name()} FAILED with error {self.error}"


class RequestCreationFailure(RequestFinishedBase):
    """
    A special class for situations where the creation of a new request fails before it was ever able to run.
    """

    def __init__(self, *, request_id: str, error: Exception):
        super().__init__(request_id=request_id, node_state=None)
        self.error = error

    def __repr__(self):
        return f"{self.__class__.__name__}(request_id={self.request_id}, error={self.error})"

    def log_message(self) -> str:
        return f"Request creation FAILED with error {self.error}"


####### Request Creation Messages ########


class RequestCreation(RequestCompletionMessage):
    """
    A message that describes the creation of a new request in the system.
    """

    def __init__(
        self,
        *,
        current_node_id: str | None,
        current_run_id: str | None,
        new_request_id: str,
        running_mode: ExecutionConfigurations,
        new_node_type: Type[Node],
        args,
        kwargs,
    ):
        self.current_node_id = current_node_id
        self.current_run_id = current_run_id
        self.new_request_id = new_request_id
        self.running_mode = running_mode
        self.new_node_type = new_node_type
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(current_node_id={self.current_node_id}, "
            f"new_request_id={self.new_request_id}, running_mode={self.running_mode}, "
            f"new_node_type={self.new_node_type.__name__}, args={self.args}, kwargs={self.kwargs})"
        )


##### OTHER MESSAGES #####


class FatalFailure(RequestCompletionMessage):
    """
    A message that indicates an irrecoverable failure in the request completion system.
    """

    def __init__(self, *, error: Exception):
        self.error = error

    def __repr__(self):
        return f"{self.__class__.__name__}(error={self.error})"


class Streaming(RequestCompletionMessage):
    """
    A message that indicates a streaming operation in the request completion system.
    """

    def __init__(self, *, streamed_object: Any, node_id: str):
        self.streamed_object = streamed_object
        self.node_id = node_id

    def __repr__(self):
        return f"{self.__class__.__name__}(streamed_object={self.streamed_object}, node_id={self.node_id})"
