from __future__ import annotations

from typing import List, TypeVar

from .utils.profiling import Stamp, StampManager
from .state.request import RequestForest
from .state.node import NodeForest
from .visuals.agent_viewer import AgentViewer


_TOutput = TypeVar("_TOutput")


# TODO add some the logic for an optional architecture requirement.
class ExecutionInfo:
    """
    A class that contains the full details of the state of a run at any given point in time.

    The class is designed to be used as a snapshot of the state which can be both used to view the state of the run and
    to be used to continue the run from the point it was saved.
    """

    def __init__(
        self,
        request_heap: RequestForest,
        node_heap: NodeForest,
        stamper: StampManager,
        exception_history: List[Exception] = None,
    ):
        self.request_heap = request_heap
        self.node_heap = node_heap
        self.stamper = stamper
        self.exception_history = exception_history or []

    @classmethod
    def default(cls):
        """Creates a new "empty" instance of the ExecutionInfo class with the default values."""
        return cls.create_new()

    @classmethod
    def create_new(
        cls,
    ) -> ExecutionInfo:
        """
        Creates a new empty instance of state variables with the provided executor configuration.

        """
        request_heap = RequestForest()
        node_heap = NodeForest()
        stamper = StampManager()

        return ExecutionInfo(
            request_heap=request_heap,
            node_heap=node_heap,
            stamper=stamper,
            exception_history=[],
        )

    @property
    def answer(self) -> _TOutput:
        """Convenience method to access the answer of the run."""
        return self.request_heap.answer

    @property
    def all_stamps(self) -> List[Stamp]:
        """Convenience method to access all the stamps of the run."""
        return self.stamper.all_stamps

    def view_graph(self):
        """A convenience method used to view a graph representation of the run."""
        AgentViewer(self.all_stamps, self.request_heap, self.node_heap).display_graph()
