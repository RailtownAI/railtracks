from __future__ import annotations

from abc import ABC
from typing import Any, Generic, Literal, ParamSpec, Type, TypeVar

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


class RequestFinishedBase(RequestCompletionMessage, ABC, Generic[_P, _TOutput, _TNode]):
    """
    A simple base class for all messages that pertain to a request finishing.
    """

    def __init__(
        self,
        *,
        request_id: str,
        node_state: NodeState[Node[_P, _TOutput]] | None,
    ):
        self.request_id = request_id
        self.node_state = node_state

    @property
    def node(self) -> Node[_P, _TOutput] | None:
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
        node_state: NodeState[Node[_P, _TOutput]],
        result: _TOutput,
    ):
        super().__init__(request_id=request_id, node_state=node_state)
        self.result = result
        self.node_state = node_state

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
        node_state: NodeState[Node[_P, _TOutput]] | None,
        error: Exception,
    ):
        super().__init__(request_id=request_id, node_state=node_state)
        self.error = error
        self.node_state = node_state

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(request_id={self.request_id}, "
            f"node_state={self.node_state}, error={self.error})"
        )

    def log_message(self) -> str:
        node_name = (
            self.node_state.node.name() if self.node_state is not None else "<unknown>"
        )
        return f"{node_name} FAILED with error {self.error}"


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

    Args:
        current_node_id: The id of the node creating this request (None for a top level request).
        current_run_id: The run id of the tree this request belongs to (None for a top level request).
        new_request_id: The unique identifier of the request being created.
        running_mode: The execution mode used to run this request.
        new_node_type: The node type to instantiate for this request.
        args: The positional arguments to pass to the node.
        kwargs: The keyword arguments to pass to the node.
        stream: If True, the created node's frame will have streaming enabled (see `rt.astream`).
            Note this flag is frame-local: it applies only to the node created by this request,
            never to its children.
        current_stream_id: The stream scope id of the *creating* frame. Children inherit this id so
            their explicit broadcasts can be routed to the consumer attached to the entry frame.
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
        stream: bool = False,
        current_stream_id: str | None = None,
    ):
        self.current_node_id = current_node_id
        self.current_run_id = current_run_id
        self.new_request_id = new_request_id
        self.running_mode = running_mode
        self.new_node_type = new_node_type
        self.args = args
        self.kwargs = kwargs
        self.stream = stream
        self.current_stream_id = current_stream_id

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


# The two kinds of broadcast traffic, kept on separate lanes so consumers never mix them up.
# "event": a one-off item published with `rt.broadcast` (progress notes, tool events, ...) —
# this is what `broadcast_callback` observes. "stream": one chunk of a continuous production
# published through `rt.broadcast_stream`, which includes all LLM token streaming — this is
# what `rt.astream` consumes and, deliberately, what `broadcast_callback` ignores.
StreamingKind = Literal["event", "stream"]


class Streaming(RequestCompletionMessage):
    """
    A message carrying a single streamed item (e.g. an LLM token chunk or a user broadcast).

    Args:
        streamed_object: The item being streamed (typically a `str` chunk).
        node_id: The id of the node that emitted the item.
        channel: The named channel this item was emitted on. Consumers can filter/route on
            this name. Defaults to `"default"`.
        stream_id: The stream scope this item belongs to. This is the request id of the entry
            frame that was invoked with streaming enabled (see `rt.astream`), or None if the
            item was broadcast outside any streaming scope.
        kind: What produced this item: `"event"` for a one-off `rt.broadcast`, `"stream"` for
            a chunk of an `rt.broadcast_stream` production (LLM token streams included). The
            two lanes are kept separate so a `broadcast_callback` (events) is never flooded
            with stream tokens; `rt.astream` consumes the stream lane, scoped by `stream_id`.
    """

    def __init__(
        self,
        *,
        streamed_object: Any,
        node_id: str | None,
        channel: str = "default",
        stream_id: str | None = None,
        kind: StreamingKind = "event",
    ):
        self.streamed_object = streamed_object
        self.node_id = node_id
        self.channel = channel
        self.stream_id = stream_id
        self.kind = kind

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(streamed_object={self.streamed_object}, "
            f"node_id={self.node_id}, channel={self.channel}, stream_id={self.stream_id}, "
            f"kind={self.kind})"
        )
