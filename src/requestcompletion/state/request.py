from __future__ import annotations

import uuid
import warnings
from dataclasses import dataclass
from functools import reduce
from typing import Optional, Dict, List, Tuple, Iterable, Set, FrozenSet, Any


from .forest import (
    Forest,
    AbstractLinkedObject,
)
from ..utils.profiling import Stamp
from ..utils.serialization.graph import Edge


class Cancelled:
    pass


class Failure:
    def __init__(self, exception: Exception):
        self.exception = exception


@dataclass(frozen=True)
class RequestTemplate(AbstractLinkedObject):
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
                "state": self.status,
                "input_args": self.input[0],
                "input_kwargs": self.input[1],
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
            return "Completed"
        else:
            return "Open"

    def get_all_parents(self):
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
        self._dead_children: Set[str] = set()
        self._failure_tree: Set[FrozenSet[RequestTemplate]] = set()

    def __getitem__(self, item):
        with self._lock:
            if item in self._dead_children:
                warnings.warn(
                    "You are attempting to access a request that has been reverted."
                )
                raise DeadRequestError(
                    "You are attempting to access a request that has been reverted."
                )
            try:
                return self._heap[item]
            except KeyError:
                print(
                    f"failed to collect a request {item in [x.identifier for x in self._full_data]}"
                )
                raise

    def failure_tree(self, at_step: int | None = None):
        """
        Gets a failure tree containing the requests that have failed. If the at_step is provided then it will only
        return the failures up to and including that step.

        Args:
            at_step (int | None): The step to collect the failures up to. If None then it will collect all the failures.

        Returns:
            Set[FrozenSet[RequestTemplate]]: A set of frozen sets containing the requests that have failed.
        """

        new_set = set()
        for tree in self._failure_tree:
            if at_step is None:
                new_set.add(set(tree))
            else:
                new_set.add({x for x in tree if x.stamp.step <= at_step})

        return new_set

    def to_edges(self):
        """
        Converts the current heap into a list of `Edge` objects.
        """
        edge_list = [request.to_edge() for request in self._heap.values()]

        return edge_list

    def collect_dead_request(self, request_id: str):
        """
        A special method to collect a request which had died via some sort of error in the system.
        """
        with self._lock:
            deads = sorted(
                [x for x in self._full_data if x.identifier == request_id],
                key=lambda x: x.stamp.step,
            )
            if len(deads) == 0:
                return None
            return deads[-1]

    def revert_heap(self, request_id: str):
        """
        This method will preform the following actions to revert the requests in the heap:
        1. It will collect the request connected the parent of the provided request
        2. Collect the children of the provided request
        4. Remove all the children from the heap (note that this is becuase all of these should have been created after
         the last completion of the parent request)
        5. Saves the list of dead children so we can access them again as needed outside the regular heap mechanism.

        Args:
            request_id (str): The request id of the request that failed and you would like to revert.

        Returns:
            Tuple[List[RequestTemplate], int, str]: A tuple containing the list of children requests that were removed,
            the step of the parent request after it was reverted, and the request id of the parent request. The parent
            request id is the next item that can be completed.

        Raises:
            DeadRequestError: If the request has already been reverted.

        """

        with self._lock:
            if request_id in self._dead_children:
                warnings.warn(
                    "You are attempting to revert a request that has already been reverted. This is ok, but nothing will be reverted."
                )
                raise DeadRequestError(
                    "You are attempting to revert a request that has already been reverted."
                )

            try:
                source_id = self._heap[request_id].source_id
            except KeyError:
                assert False

            # we need to return the request where the source_id is the sink_id to its previous state.
            upstream_request_list = RequestTemplate.upstream(
                self._heap.values(), source_id
            )

            # if the failed request is the start request it will need to be handled on a special case basis
            if len(upstream_request_list) == 0:
                all_children = []
                upstream_request = self._heap[request_id]
            elif len(upstream_request_list) == 1:
                upstream_request = upstream_request_list[0]

                all_children = RequestTemplate.all_downstream(
                    self._heap.values(), source_id
                )
            else:
                assert False, "There should never be more than 1 upstream request"

            # note the upstream request contains the stamp we care about
            # it is assumed that the upstream request is at the state when the request was completed
            new_upstream_request = upstream_request
            assert new_upstream_request is not None, (
                f"Fix this bug here {upstream_request}"
            )
            for child in all_children:
                assert child.stamp.step > new_upstream_request.stamp.step, (
                    "All children should have been created in the future of this request."
                )
                del self._heap[child.identifier]

            # finally we revert that upstream_request
            self._heap[upstream_request.identifier] = new_upstream_request

            self._dead_children.update([x.identifier for x in all_children])
            try:
                failed_elements = set(all_children)

            except TypeError as e:
                print("\n".join([repr(x) for x in all_children]))
                print(e)
                raise

            self._failure_tree.add(frozenset(failed_elements))
            return (
                all_children,
                new_upstream_request.stamp.step,
                upstream_request.identifier,
            )

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
    ):
        """
        Updates the heap with the provided request details. Note you must call this function on a request that exist in the heap.

        The function will replace the old request with a new updated one with the provided output attached to the provided stamp.

        I will outline the special cases for this function:
        1. If the request you are trying to update has already been killed, then nothing will happen.
        2. If you have provided a request id that does not exist in the heap, it will raise `RequestDoesNotExistError`

        Args:
            identifier (str): The identifier of the request
            output (Optional[RequestOutput]): The output of the request, None if the request is not completed.
            stamp (Stamp): The stamp that you would like this request addition to be tied to.

        Returns:
            Optional[str]: The identifier of the next request to be completed. If None then there is no request that is
            ready to be completed.

        Raises:

        """
        with self._lock:
            if identifier in self._dead_children:
                warnings.warn(
                    "You are attempting to update a request that has been reverted. This is ok, but nothing will be updated."
                )
                return None

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
        Generates a dictionary representation containg the edges in the graph. The key of the dictionary is the source
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
        Checks if all the downstream requests (one level down) of the given parent node are complete. If they are
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
        insertions = [v for v in self._heap.values() if v.source_id is None]

        return insertions

    @property
    def answer(self):
        # first we must find the insertion request

        if len(self.insertion_request) == 0:
            return None
        if len(self.insertion_request) > 1:
            return [x.output for x in self.insertion_request]
        else:
            return self.insertion_request[0].output


class DeadRequestError(Exception):
    """
    A special exception to be thrown when the request you are looking collect has been killed during a scorched earth
     process
    """

    pass


class RequestDoesNotExistError(Exception):
    """
    A special exception to be thrown when you are trying to update a Request which does not exist.
    """

    pass


class RequestAlreadyExistsError(Exception):
    pass
