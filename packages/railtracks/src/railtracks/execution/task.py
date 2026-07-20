from typing import Any, Generic, TypeVar

from railtracks.context.central import get_run_id, update_parent_id
from railtracks.nodes.nodes import Node

_TOutput = TypeVar("_TOutput")


class Task(Generic[_TOutput]):
    """
    A simple class used to represent a task to be completed.
    """

    # Note this class is a simple abstraction of a task that can be executed (see `Command` design pattern).

    def __init__(
        self,
        request_id: str,
        node: Node[..., _TOutput],
        arguments: tuple[tuple, dict[str, Any]],
        stream: bool = False,
    ):
        self.request_id = request_id
        self.node = node
        self.arguments = arguments
        # when True the node's frame will run with streaming enabled (frame-local, see rt.astream)
        self.stream = stream

    async def invoke(self):
        """The callable that this task is representing."""
        # if this frame is the entry of a streamed invocation, its request id becomes the
        # stream scope id used to route broadcast chunks back to the consumer.
        stream_id = self.request_id if self.stream else None

        # if there is no parent run_id then this is the root
        if get_run_id() is None:
            # note critically that since these variables only this tree of requests will see this run_id.
            update_parent_id(
                self.node.uuid, self.node.uuid, stream=self.stream, stream_id=stream_id
            )

        # otherwise we are already in a run so we just use the previous one.
        else:
            update_parent_id(self.node.uuid, stream=self.stream, stream_id=stream_id)

        result = await self.node.wrapped_invoke(*self.arguments[0], **self.arguments[1])

        return result
