from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import reduce
from typing import Any, Dict, Iterable, List, Optional, Tuple

from railtracks.utils.profiling import Stamp
from railtracks.utils.serialization.graph import Edge

from .forest import (
    AbstractLinkedObject,
    Forest,
)


class Cancelled:
    pass


class Failure:
    def __init__(self, exception: Exception):
        self.exception = exception


@dataclass(frozen=True)
class RequestTemplate(AbstractLinkedObject):
    """
    A simple object containing details about a request in the system.
    """

    source_id: Optional[str]
    sink_id: str
    input: Tuple[Tuple, Dict]
    output: Optional[Any]
    parent: Optional[RequestTemplate]

    def __repr__(self):
        return f"RequestTemplate({self.identifier}, {self.source_id}, {self.sink_id}, {self.output}, {self.stamp})"

    def to_edge(self):
        """
        Converts the request template to an edge representation.
        """
        return Edge(
            source=self.source_id,
            target=self.sink_id,
            identifier=self.identifier,
            stamp=self.stamp,
            details={
                "input_args": self.input[0],
                "input_kwargs": self.input[1],
                "status": self.status,
                "output": self.output,
            },
            parent=self.parent.to_edge() if self.parent is not None else None,
        )

    @property
    def closed(self):
        """
        If the request has an output it is closed
        """
        return self.output is not None

    @property
    def is_insertion(self):
        """
        If the request is an insertion request it will return True.
        """
        return self.source_id is not None

    @property
    def status(self):
        """
        Gets the current status of the request.
        """

        if self.output is not None:
            if isinstance(self.output, Failure):
                return "Failed"

            return "Completed"
        else:
            return "Open"

    def get_all_parents(self) -> List[RequestTemplate]:
        """
        Recursely collects all the parents for the request.
        """
        if self.parent is None:
            return [self]
        return [self] + self.parent.get_all_parents()

    @property
    def get_terminal_parent(self):
        """
        Returns the terminal parent of the request.

        If this request is the parent then it will return itself.
        """
        if self.parent is not None:
            return self.parent.get_terminal_parent
        return self

    @property
    def duration_detail(self):
        """
        Returns the difference in time between the parent and the current request stamped time.
        """
        total_time = self.stamp.time - self.get_terminal_parent.stamp.time

        return total_time

    @classmethod
    def generate_id(cls):
        """
        Generates a new unique identifier for the request. This is suitable for use as a request identifier.
        """
        return str(uuid.uuid4())

    @classmethod
    def downstream(cls, requests: Iterable[RequestTemplate], source_id: Optional[str]):
        """Collects the requests one level downstream from the provided source_id."""
        return [x for x in requests if x.source_id == source_id]

    @classmethod
    def upstream(cls, requests: Iterable[RequestTemplate], sink_id: str):
        """Collects the requests one level upstream from the provided sink_id."""
        return [x for x in requests if x.sink_id == sink_id]

    @classmethod
    def all_downstream(
        cls, requests: Iterable[RequestTemplate], source_id: Optional[str]
    ):
        """
        Collects all the downstream requests from the provided source_id.
        """
        downstream_requests = cls.downstream(requests, source_id)
        additions = []
        for x in downstream_requests:
            additions += cls.all_downstream(requests, x.sink_id)

        return downstream_requests + additions

    @classmethod
    def open_tails(cls, requests: Iterable[RequestTemplate], source_id: Optional[str]):
        """
        Traverses down the provided tree to find all the open tails.

        Open Tail: is defined as any node which currently holds an open request and does not have any open ones beneath
        it.
        """
        open_downstream_requests = [
            x for x in cls.downstream(requests, source_id) if not x.closed
        ]

        # BASE CASE
        if len(open_downstream_requests) == 0:
            open_upstreams = cls.upstream(requests, source_id)
            assert len(open_upstreams) <= 1, (
                f"There should only be one or 0 upstream request, instead there was {len(open_upstreams)}"
            )
            return [r for r in open_upstreams if not r.closed]

        # RECURSIVE CASE
        return reduce(
            lambda x, y: x + y,
            [cls.open_tails(requests, x.sink_id) for x in open_downstream_requests],
            [],
        )

    @classmethod
    def children_complete(
        cls, requests: Iterable[RequestTemplate], source_node_id: str
    ):
        """
        Checks if all the downstream requests of a given parent node are complete. If so returns True.
         Otherwise, returns False.
        """
        downstream_requests = cls.downstream(requests, source_node_id)

        return all(x.closed for x in downstream_requests)


class RequestForest(Forest[RequestTemplate]):
    def __init__(
        self,
        request_heap: Dict[str, RequestTemplate] | None = None,
    ):
        """
        Creates a new instance of a request heap with no objects present.
        """
        super().__init__(heap=request_heap)

    def __getitem__(self, item):
        with self._lock:
            try:
                return self._heap[item]
            except KeyError:
                print(
                    f"failed to collect a request {item in [x.identifier for x in self._full_data]}"
                )
                raise

    def to_edges(self):
        """
        Converts the current heap into a list of `Edge` objects.
        """
        edge_list = [request.to_edge() for request in self._heap.values()]

        return edge_list

    def create(
        self,
        identifier: str,
        source_id: Optional[str],
        sink_id: str,
        input_args: Tuple,
        input_kwargs: Dict,
        stamp: Stamp,
    ):
        """
        Creates a new instance of a request from the provided details and places it into the heap.

        Args:
            identifier (str): The identifier of the request
            source_id (Optional[str]): The node id of the source, None if it is an insertion request.
            sink_id (str): The node id in the sink.
            input_args (Tuple): The input arguments for the request
            input_kwargs (Dict): The input keyword arguments for the request
            stamp (Stamp): The stamp that you would like this request to be tied to.

        Returns:
            str: The identifier of the request that was created.

        """
        # note we just need t be careful of any sort of race condition so we will be extra safe with our locking mechanism.
        with self._lock:
            if identifier in self._heap:
                raise RequestAlreadyExistsError(
                    f"You are trying to create a request {identifier} which already exists. "
                )

            new_request = RequestTemplate(
                identifier=identifier,
                source_id=source_id,
                sink_id=sink_id,
                input=(input_args, input_kwargs),
                output=None,
                stamp=stamp,
                parent=None,
            )

            self._update_heap(new_request)
            return identifier

    def update(
        self,
        identifier: str,
        output: Optional[Any],
        stamp: Stamp,
    ) -> None:
        """
        Updates the heap with the provided request details. Note you must call this function on a request that exist in the heap.

        The function will replace the old request with a new updated one with the provided output attached to the provided stamp.

        I will outline the special cases for this function:
        1. If you have provided a request id that does not exist in the heap, it will raise `RequestDoesNotExistError`

        Args:
            identifier (str): The identifier of the request
            output (Optional[RequestOutput]): The output of the request, None if the request is not completed.
            stamp (Stamp): The stamp that you would like this request addition to be tied to.

        Raises:
            RequestDoesNotExistError: If the request with the provided identifier does not exist in the heap.

        """
        with self._lock:
            old_request = self._heap.get(identifier, None)

            # one cannot update a request that does not exist
            if old_request is None:
                raise RequestDoesNotExistError(
                    f"Request with identifier {identifier} does not exist in the heap."
                )

            linked_request = RequestTemplate(
                identifier=identifier,
                source_id=old_request.source_id,
                sink_id=old_request.sink_id,
                input=old_request.input,
                output=output,
                stamp=stamp,
                parent=self._heap.get(identifier, None),
            )
            self._update_heap(linked_request)

    def children(self, parent_id: str):
        """
        Finds all the children of the provided parent_id.
        """
        with self._lock:
            return RequestTemplate.downstream(self._heap.values(), parent_id)

    @classmethod
    def generate_graph(
        cls, heap: Dict[str, RequestTemplate]
    ) -> Dict[str, List[Tuple[str, str]]]:
        """
        Generates a dictionary representation contain the edges in the graph. The key of the dictionary is the source
        and the value is a list of tuples where the first element is the sink_id and the second element is the request\
        id.
        Complexity: O(n) where n is the number of identifiers in the heap.

        Args:
            heap (Dict[str, RequestTemplate]): The heap of requests to generate the graph from.

        Returns:
            Dict[str, List[Tuple[str, str]]]: The graph representation of the heap.

        """

        # graph structure includes the request id and the source and sink id.
        # the tuple will be the sink id followed by the request id.
        graph: Dict[str, List[Tuple[str, str]]] = {}
        for request_temp in heap.values():
            if request_temp.source_id not in graph:
                graph[request_temp.source_id] = []
            if request_temp.sink_id not in graph:
                graph[request_temp.sink_id] = []

            graph[request_temp.source_id].append(
                (request_temp.sink_id, request_temp.identifier)
            )

        return graph

    def get_request_from_child_id(self, child_id: str):
        """
        Gets the request where this child_id is the sink_id of the request.

        Via the invariants of the system. There must only be 1 request that satisfies the above requirement.
        """
        with self._lock:
            upstreams = RequestTemplate.upstream(list(self._heap.values()), child_id)
            if len(upstreams) == 0:
                raise RequestDoesNotExistError(
                    f"Request with child id {child_id} does not exist in the heap."
                )
            assert len(upstreams) == 1, (
                f"Expected 1 upstream request, instead got {len(upstreams)}"
            )
            return upstreams[0]

    def open_tails(self):
        """
        Collects the current open tails in the heap. See `RequestTemplate.open_tails` for more information.
        """
        # the insertion request will have a none source_id
        with self._lock:
            o_t = RequestTemplate.open_tails(list(self._heap.values()), None)
            return o_t

    def children_requests_complete(self, parent_node_id: str):
        """
        Checks if all the downstream requests (one level down) if the given parent node are complete. If they are
         then it will return the request id of the parent node. Otherwise, it will return None.

        Note that you are providing the node_id of the parent node and downstream requests of that node is defined
         as any of the requests which have the matching parent_node.

        Args:
            parent_node_id (str): The parent node id

        Returns:
            The request_id string of the parent node if all the children are complete otherwise None.
        """

        with self._lock:
            if RequestTemplate.children_complete(
                list(self._heap.values()), parent_node_id
            ):
                upstreams = RequestTemplate.upstream(
                    list(self._heap.values()), parent_node_id
                )
                assert len(upstreams) == 1, (
                    f"Expected 1 upstream request, instead got {len(upstreams)}"
                )
                return upstreams[0].identifier
            return None

    @property
    def insertion_request(self):
        """
        Collects a list of all the insertion requests in the heap.

        They will be returned in the order that they were created.
        """
        insertions = [v for v in self._heap.values() if v.source_id is None]

        return insertions

    @property
    def answer(self):
        """
        Collects the answer to the insertion request.

        The behavior of the function can be split into two cases:

        1. There is either 1 or 0 insertion requests present:
         - In this case, it will return the output of the insertion request if it exists, otherwise None

        2. There is more than 1 insertion request:
         - Returns an ordered list of outputs of all the insertion requests. If one has not yet completed, it will
           return None in that index.
        """
        # first we must find the insertion request

        if len(self.insertion_request) == 0:
            return None
        if len(self.insertion_request) > 1:
            return [x.output for x in self.insertion_request]
        else:
            return self.insertion_request[0].output


class RequestDoesNotExistError(Exception):
    """
    A special exception to be thrown when you are trying to update a Request which does not exist.
    """

    pass


class RequestAlreadyExistsError(Exception):
    pass
