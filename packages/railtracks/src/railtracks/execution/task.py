import asyncio
from typing import Any, Generic, TypeVar

from railtracks.context.central import push_stream_queue
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
        stream_queue: asyncio.Queue[Any] | None = None,
    ):
        self.request_id = request_id
        self.node = node
        self.arguments = arguments
        # when set, this frame is the entry of a streamed invocation: its LLM node writes each
        # token chunk onto this queue, which the rt.astream handle drains (frame-local).
        self.stream_queue = stream_queue

    async def invoke(self):
        """The callable that this task is representing."""
        if self.stream_queue is not None:
           push_stream_queue(self.stream_queue)
           
        result = await self.node.wrapped_invoke(*self.arguments[0], **self.arguments[1])

        return result
