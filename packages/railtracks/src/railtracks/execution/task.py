from typing import Any, Generic, TypeVar

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
    ):
        self.request_id = request_id
        self.node = node
        self.arguments = arguments

    async def invoke(self):
        """The callable that this task is representing."""
        result = await self.node.wrapped_invoke(*self.arguments[0], **self.arguments[1])

        return result
