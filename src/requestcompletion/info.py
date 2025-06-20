from __future__ import annotations

from typing import List, TypeVar

from .state.utils import create_sub_state_info
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

    @property
    def insertion_requests(self):
        """A convenience method to access all the insertion requests of the run."""
        return self.request_heap.insertion_request

    def get_info(self, ids: List[str] | str | None = None) -> ExecutionInfo:
        """
        Gets a subset of the current state based on the provided node ids. It will contain all the children of the provided node ids

        Note: If no ids are provided, the full state is returned.

        Args:
            ids (List[str] | str | None): A list of node ids to filter the state by. If None, the full state is returned.

        Returns:
            ExecutionInfo: A new instance of ExecutionInfo containing only the children of the provided ids.

        """
        if ids is None:
            return self
        else:
            # firstly lets
            if isinstance(ids, str):
                ids = [ids]

            # we need to quickly check to make sure these ids are valid
            for identifier in ids:
                if identifier not in self.request_heap:
                    raise ValueError(
                        f"Identifier '{identifier}' not found in the current state."
                    )

            new_node_forest, new_request_forest = create_sub_state_info(
                self.node_heap.heap(),
                self.request_heap.heap(),
                ids,
            )
            return ExecutionInfo(
                node_heap=new_node_forest,
                request_heap=new_request_forest,
                stamper=self.stamper,
                exception_history=list(self.exception_history),
            )

    def view_graph(self):
        """A convenience method used to view a graph representation of the run."""
        AgentViewer(self.all_stamps, self.request_heap, self.node_heap).display_graph()
