from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, ParamSpec, Type

from railtracks.nodes.nodes import (
    Node,
)
from railtracks.utils.profiling import Stamp
from railtracks.utils.serialization.graph import Vertex

from .forest import (
    AbstractLinkedObject,
    Forest,
)

_P = ParamSpec("_P")


@dataclass(frozen=True)
class LinkedNode(AbstractLinkedObject):
    """
    A simple class that allows you store a `Node` in abstract linked object.
    """

    _node: Node  # have to be careful here because Node objects are mutable.
    parent: Optional[LinkedNode]

    def to_vertex(self):
        return Vertex(
            identifier=self.identifier,
            node_type=self.node.type(),
            name=self.node.name(),
            stamp=self.stamp,
            details={"internals": self.node.details},
            parent=self.parent.to_vertex() if self.parent else None,
        )

    @property
    def node(self):
        """
        A passed by value copy of a node contained in this object.

        IMPORTANT: This method will run the `safe_copy` method of the node when accessing it.
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

        self.id_type_mapping: Dict[str, Type[Node]] = (
            {node.identifier: type(node.node) for node in node_heap.values()}
            if node_heap
            else {}
        )

    def __getitem__(self, item):
        """
        Collects the node of the given id from the heap.

        Note it will throw a NodeCopyError if the node cannot be copied.
        """

        node = self._heap[item]
        return node

    def to_vertices(self):
        """
        Converts the current heap into a list of `Vertex` objects.
        """
        full_nodes = [n.to_vertex() for n in self._heap.values()]

        return full_nodes

    def update(self, new_node: Node, stamp: Stamp):
        """
        Updates the heap with the provided node. If you are updating a node that is currently present in the heap you
        must provide the passcode that was returned when you collected the node. You should set passcode to None if this
        is a new node.

        Args:
            new_node (Node): The node to update the heap with (it could have the same id as one already in the heap)
            stamp (Stamp): The stamp you would like to attach to this node update.

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
        """
        Gets the type of the node with the provided identifier.
        """
        return self.id_type_mapping.get(identifier, None)
