from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from typing_extensions import Self

if TYPE_CHECKING:
    from railtracks.utils.profiling import Stamp


class Edge:
    def __init__(
        self,
        *,
        identifier: str | None,
        source: str | None = None,
        target: str,
        stamp: Stamp,
        details: dict[str, Any],
        parent: Self | None = None,
    ):
        """
        A simple representation of an edge in a graph structure.

        This type is designed to be used as a request in the system and should not be extended for other uses.

        Args:
            identifier (str | None): The unique identifier for the edge.
            source (str | None): The source vertex of the edge. None can be expected if the input does not have a source
            target (str): The target (sink) vertex of the edge.
            stamp (Stamp): A timestamp that is attached to this edge.
            details (dict[str, Any]): Additional details about the edge, which can include any relevant information.
            parent (Edge | None): An optional parent edge, this item should represent the temporal parent of the edge.
        """
        self.identifier = identifier
        self.source = source
        self.target = target
        self.stamp = stamp
        self.details = details
        assert parent is None or parent.identifier == identifier, (
            "The parent identifier must match the edge identifier"
        )
        assert parent is None or (
            parent.source == source and parent.target == target
        ), "The parent edge must have the same source and target"
        self.parent = parent


class Vertex:
    def __init__(
        self,
        *,
        identifier: str,
        node_type: Literal["Tool", "Agent", "Other"],
        name: str,
        stamp: Stamp,
        details: dict[str, Any],
        parent: Self | None,
    ):
        """
        The Vertex class represents a single vertex in a graph structure.

        This class is designed to encapsulate the properties that a node would have and should not be extended for use
        cases outside of that

        Args:
            identifier (str): The unique identifier for the vertex.
            node_type (str): The type of the node, which can be used to differentiate between different kinds of nodes.
            stamp (Stamp): A timestamp that represents a timestamp attached this vertex.
            details (dict[str, Any]): Additional details about the vertex, which can include any relevant information.
            Often times this should contain
            parent (Vertex | None): An optional parent vertex, this item should represent the temporal parent of the vertex.
        """
        self.identifier = identifier
        self.node_type = node_type
        self.details = details
        self.stamp = stamp
        self.name = name
        assert parent is None or parent.identifier == identifier, (
            "The parent identifier must match the vertex identifier"
        )
        self.parent = parent
