from typing import TypeVar, Generic

from ..context.central import update_parent_id
from ..nodes.nodes import Node

_TOutput = TypeVar("_TOutput")


class Task(Generic[_TOutput]):
    """A simple class used to represent a task to be completed by the executor of choice."""

    def __init__(
        self,
        request_id: str,
        node: Node[_TOutput],
    ):
        self.request_id = request_id
        self.node = node

    async def invoke(self):
        """The callable that this task is representing."""
        update_parent_id(self.node.uuid)
        return await self.node.tracked_invoke()
