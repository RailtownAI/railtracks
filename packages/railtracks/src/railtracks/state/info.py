from __future__ import annotations

import json
from typing import Any, List, Tuple, TypeVar

from railtracks.utils.profiling import Stamp, StampManager
from railtracks.utils.serialization.graph import Edge, Vertex

from .node import NodeForest
from .request import RequestForest
from .serialize import RTJSONEncoder
from .utils import create_sub_state_info

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
        request_forest: RequestForest,
        node_forest: NodeForest,
        stamper: StampManager,
    ):
        self.request_forest = request_forest
        self.node_forest = node_forest
        self.stamper = stamper

    @classmethod
    def default(cls) -> ExecutionInfo:
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
            request_forest=request_heap,
            node_forest=node_heap,
            stamper=stamper,
        )

    @property
    def answer(self):
        """Convenience method to access the answer of the run."""
        return self.request_forest.answer

    @property
    def all_stamps(self) -> List[Stamp]:
        """Convenience method to access all the stamps of the run."""
        return self.stamper.all_stamps

    @property
    def name(self):
        """
        Gets the name of the graph by pulling the name of the insertion request. It will raise a ValueError if the insertion
        request is not present or there are multiple insertion requests.
        """
        insertion_requests = self.insertion_requests

        if len(insertion_requests) >= 2:
            raise ValueError(
                "You cannot get the name of a graph with multiple insertion requests"
            )

        if len(insertion_requests) == 0:
            raise ValueError(
                "You cannot get the name of a graph with no insertion requests"
            )

        i_r = insertion_requests[0]

        return self.node_forest.get_node_type(i_r.sink_id).name()

    @property
    def insertion_requests(self):
        """A convenience method to access all the insertion requests of the run."""
        return self.request_forest.insertion_request

    def _get_info(self, ids: List[str] | str | None = None) -> ExecutionInfo:
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
                if identifier not in self.request_forest:
                    raise ValueError(
                        f"Identifier '{identifier}' not found in the current state."
                    )

            new_node_forest, new_request_forest = create_sub_state_info(
                self.node_forest.heap(),
                self.request_forest.heap(),
                ids,
            )
            return ExecutionInfo(
                node_forest=new_node_forest,
                request_forest=new_request_forest,
                stamper=self.stamper,
            )

    def _to_graph(self) -> Tuple[List[Vertex], List[Edge]]:
        """
        Converts the current state into its graph representation.

        Returns:
            List[Node]: An iterable of nodes in the graph.
            List[Edge]: An iterable of edges in the graph.
        """
        return self.node_forest.to_vertices(), self.request_forest.to_edges()

    def graph_serialization(self) -> dict[str, Any]:
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


        ```
        """
        parent_nodes = [x.identifier for x in self.insertion_requests]

        infos = [self._get_info(parent_node) for parent_node in parent_nodes]

        runs = []

        for info, parent_node_id in zip(infos, parent_nodes):
            insertion_requests = info.request_forest.insertion_request

            assert len(insertion_requests) == 1
            parent_request = insertion_requests[0]

            all_parents = parent_request.get_all_parents()

            start_time = all_parents[-1].stamp.time

            assert len([x for x in all_parents if x.status == "Completed"]) <= 1
            end_time = None
            for req in all_parents:
                if req.status in ["Completed", "Failed"]:
                    end_time = req.stamp.time
                    break

            entry = {
                "name": info.name,
                "run_id": parent_node_id,
                "nodes": info.node_forest.to_vertices(),
                "status": parent_request.status,
                "edges": info.request_forest.to_edges(),
                "steps": _get_stamps_from_forests(
                    info.node_forest, info.request_forest
                ),
                "start_time": start_time,
                "end_time": end_time,
            }
            runs.append(entry)

        return json.loads(
            json.dumps(
                runs,
                cls=RTJSONEncoder,
            )
        )


def _get_stamps_from_forests(
    node_forest: NodeForest,
    request_forest: RequestForest,
):
    node_stamps = {n.stamp for n in node_forest.full_data()}
    request_stamps = {r.stamp for r in request_forest.full_data()}

    result = sorted(node_stamps.union(request_stamps))

    return result
