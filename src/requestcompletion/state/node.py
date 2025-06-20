from __future__ import annotations


import warnings

from dataclasses import dataclass
from typing import Optional, Iterable, ParamSpec, Dict, Type

from .forest import (
    AbstractLinkedObject,
    Forest,
)
from ..utils.profiling import Stamp
from ..nodes.nodes import (
    Node,
)

_P = ParamSpec("_P")


@dataclass(frozen=True)
class LinkedNode(AbstractLinkedObject):
    """
    A simple class that allows you store a `Node` in abstract linked object.
    """

    _node: Node  # have to be careful here because Node objects are mutable.
    parent: Optional[LinkedNode]

    @property
    def node(self):
        """
        A passed by value copy of a node contained in this object.
        """
        try:
            # special handling for
            return self._node.safe_copy()
        except Exception as e:
            raise NodeCopyError(
                "Every node must be able to be deep copied. Failed to copy node {0}, due to {1}.".format(
                    self.identifier, e
                )
            )


class NodeCopyError(Exception):
    """An exception thrown when a node cannot be copied due to a given error"""


class NodeForest(Forest[LinkedNode]):
    def __init__(self, node_heap: Dict[str, LinkedNode] | None = None):
        """
        Creates a new instance of a node heap with no objects present.
        """
        super().__init__(node_heap)

        self._hard_revert_list = set()
        self.id_type_mapping: Dict[str, Type[Node]] = (
            {node.identifier: type(node.node) for node in node_heap.values()}
            if node_heap
            else {}
        )
        self.registration_details = None

    def __getitem__(self, item):
        """
        Collects the node of the given id from the heap.

        Note it will throw a NodeCopyError if the node cannot be copied.
        """

        node = self._heap[item]
        return node

    def update(self, new_node: Node, stamp: Stamp):
        """
        Updates the heap with the provided node. If you are updating a node that is currently present in the heap you
        must provide the passcode that was returned when you collected the node. You should set passcode to None if this
        is a new node.

        Args:
            new_node (Node): The node to update the heap with (it could have the same id as one already in the heap)
            stamp (Stamp): The stamp you would like to attatch the this node update.

        Raises:

        """
        with self._lock:
            parent = self._heap.get(new_node.uuid, None)

            new_linked_node = LinkedNode(
                identifier=new_node.uuid,
                _node=new_node,
                stamp=stamp,
                parent=parent,
            )
            self._update_heap(new_linked_node)
            self.id_type_mapping[str(new_node.uuid)] = type(new_node)

    def get_node_type(self, identifier: str):
        return self.id_type_mapping.get(identifier, None)

    def hard_revert(self, node_ids: Iterable[str], to_step: int):
        """
        Preforms a hard revert on all the nodes in the heap that have the provided ids back to the provided step.

        By "Hard", that means that even if there a node which is currently being updated, it will be reverted back to
        the provided step regardless of the updates that are provided to it. To prevent against race conditions any
        nodes which are already being updated will wait for those updates to be complete for them to be removed.

        Args:
            node_ids (Iterable[str]): The ids of the nodes you would like to revert
            to_step (int): The step you would like to revert the nodes to.

        Raises:
            KeyError: If any of the provided node_ids are not in the heap.
        """
        with self._lock:
            for node_id in node_ids:
                if node_id not in self._heap:
                    warnings.warn("Node with id {0} not in heap.".format(node_id))

                # in the below code we will iterate backwards until we have gotten to valid node
                item = self._heap[node_id]
                while item is not None and item.stamp.step > to_step:
                    item = item.parent
                if item is None:
                    del self._heap[node_id]
                else:
                    self._heap[node_id] = item


class ConcurrentNodeUpdatesError(Exception):
    """A special exception used to signify when you are trying to update a node which is already being updated"""

    pass


class NodeUpdatePasscodeError(Exception):
    """A special exception used to signify when you are trying to update a node with the wrong passcode"""

    pass


class IllegalNodeAccessError(Exception):
    """
    A special exception used to signify when you are trying to access a node in the heap without using the
     concurrency protection
    """

    pass
