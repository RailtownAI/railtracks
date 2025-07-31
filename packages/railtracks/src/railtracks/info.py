from __future__ import annotations

import json
from typing import List, Tuple, TypeVar

from railtracks.utils.serialization import RTJSONEncoder

from .state.node import NodeForest
from .state.request import RequestForest
from .state.utils import create_sub_state_info
from .utils.profiling import Stamp, StampManager
from .utils.serialization.graph import Edge, Vertex

_TOutput = TypeVar("_TOutput")


# TODO add some the logic for an optional architecture requirement.
class ExecutionInfo:
    """
    A class that contains the full details of the state of a run at any given point in time.

    The class is designed to be used as a snapshot of state that can be used to display the state of the run, or to
    create a graphical representation of the system.
    """

    def __init__(
        self,
        request_heap: RequestForest,
        node_heap: NodeForest,
        stamper: StampManager,
    ):
        self.request_heap = request_heap
        self.node_heap = node_heap
        self.stamper = stamper

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
        )

    @property
    def answer(self):
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
            )

    def to_graph(self) -> Tuple[List[Vertex], List[Edge]]:
        """
        Converts the current state into its graph representation.

        Returns:
            List[Node]: An iterable of nodes in the graph.
            List[Edge]: An iterable of edges in the graph.
        """
        return self.node_heap.to_vertices(), self.request_heap.to_edges()

    def graph_serialization(self) -> str:
        """
                Creates a string (JSON) representation of this info object designed to be used to construct a graph for this
                info object.

                Some important notes about its structure are outlined below:
                - The `nodes` key contains a list of all the nodes in the graph, represented as `Vertex` objects.
                - The `edges` key contains a list of all the edges in the graph, represented as `Edge` objects.
                - The `stamps` key contains an ease of use list of all the stamps associated with the run, represented as `Stamp` objects.

                - The "nodes" and "requests" key will be outlined with normal graph details like connections and identifiers in addition to a loose details object.
                - However, both will carry an addition param called "stamp" which is a timestamp style object.
                - They also will carry a "parent" param which is a recursive structure that allows you to traverse the graph in time.

                The current schema looks something like the following.
                ```json
        {
          "nodes": [
            {
              "identifier": str,
              "node_type": str,
              "stamp": {
                 "step": int,
                 "time": float,
                 "identifier": str
              }
              "details": {
                 "internals": {
                    "latency": float,
                    <any other debugging details specific to that node type (i.e. LLM nodes)>
              }
              "parent": <recursive the same as above | terminating when this param is null>
          ]
          "edges": [
            {
              "source": str | null,
              "target": str,
              "indentifier": str,
              "stamp": {
                "step": int,
                "time": float,
                "identifier": str
              }
              "details": {
                 "input_args": [<list of input args>],
                 "input_kwargs": {<dict of input kwargs>},
                 "output": Any
              }
              "parent": <recursive, the same as above | terminating when this param is null>
            }
          ],
          "stamps": [
            {
               "step": int,
               "time": float,
               "identifier: str
            }
          ]
        }
        ```
        """
        return json.dumps(
            {
                "nodes": self.node_heap.to_vertices(),
                "edges": self.request_heap.to_edges(),
                "steps": self.all_stamps,
            },
            cls=RTJSONEncoder,
        )
