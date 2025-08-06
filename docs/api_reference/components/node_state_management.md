# Node State Management

The Node State Management component is responsible for managing a collection of linked nodes, supporting operations such as storing, updating, and retrieving nodes within a structured framework. This component is crucial for maintaining the state and history of nodes in a way that allows for efficient access and manipulation.

**Version:** 0.0.1

**Component Contact:** @github_username

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The Node State Management component is designed to handle the lifecycle of nodes within a system. It provides mechanisms to store nodes, update their state, and retrieve them efficiently. This is particularly useful in scenarios where nodes represent entities with mutable states that need to be tracked over time.

### 1.1 Storing Nodes

The component allows for the storage of nodes in a structured manner, ensuring that each node is linked to its parent, if applicable. This hierarchical storage is essential for maintaining the integrity of node relationships.

python
node_forest = NodeForest()
node_forest.update(new_node, stamp)


### 1.2 Retrieving Nodes

Nodes can be retrieved from the component using their unique identifiers. This retrieval process ensures that the most recent state of the node is accessed.

python
node = node_forest['node_id']


## 2. Public API

### `class NodeForest(Forest[LinkedNode])`
No docstring found.

#### `.__init__(self, node_heap)`
Creates a new instance of a node heap with no objects present.

#### `.to_vertices(self)`
Converts the current heap into a list of `Vertex` objects.

#### `.update(self, new_node, stamp)`
Updates the heap with the provided node. If you are updating a node that is currently present in the heap you
must provide the passcode that was returned when you collected the node. You should set passcode to None if this
is a new node.

Args:
    new_node (Node): The node to update the heap with (it could have the same id as one already in the heap)
    stamp (Stamp): The stamp you would like to attach to this node update.

Raises:

#### `.get_node_type(self, identifier)`
Gets the type of the node with the provided identifier.


---

## 3. Architectural Design

The Node State Management component is built around the concept of a `Forest`, which is a collection of `LinkedNode` objects. Each `LinkedNode` is an instance of `AbstractLinkedObject` and represents a node in the system. The design leverages immutability and thread safety to ensure consistent state management.

### 3.1 Core Design Principles

- **Immutability:** Nodes are stored as immutable objects to prevent unintended side effects during state manipulation.
- **Thread Safety:** The component uses locks to ensure that updates to the node heap are thread-safe.
- **Hierarchical Structure:** Nodes are linked to their parents, forming a tree-like structure that facilitates efficient traversal and state management.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- The component relies on the `Node` class from `railtracks.nodes.nodes` and the `Stamp` class from `railtracks.utils.profiling`.
- Ensure that the `Node` class implements a `safe_copy` method for deep copying.

### 4.2 Performance & Limitations

- The component is designed to handle a large number of nodes efficiently, but performance may degrade with extremely large datasets.
- The `time_machine` method allows for reverting the state of nodes to a previous step, which can be resource-intensive.

## 5. Related Files

### 5.1 Code Files

- [`node.py`](../packages/railtracks/src/railtracks/state/node.py): Contains the implementation of the Node State Management component.
- [`forest.py`](../packages/railtracks/src/railtracks/state/forest.py): Provides the `Forest` and `AbstractLinkedObject` classes used by the component.

### 5.2 Related Component Files

- [`node.md`](../docs/system_internals/node.md): Documentation on the node execution flow and its integration within the system.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
