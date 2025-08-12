# Execution Info

The `ExecutionInfo` component captures the state of a system run at any given point, providing a snapshot for display or graphical representation. It is designed to be used as a snapshot of state that can be used to display the state of the run or to create a graphical representation of the system.

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

The `ExecutionInfo` component is primarily used to capture and represent the state of a system's execution at any given point in time. This is crucial for debugging, monitoring, and visualizing the flow of data and control within the system.

### 1.1 Capturing Execution State

The `ExecutionInfo` class provides a comprehensive snapshot of the system's state, including nodes, requests, and timestamps.

python
from railtracks.state.info import ExecutionInfo

# Create a new execution info instance
execution_info = ExecutionInfo.create_new()

# Access the answer of the run
answer = execution_info.answer

# Get all stamps
stamps = execution_info.all_stamps


### 1.2 Graphical Representation

The component can convert the current state into a graph representation, which can be serialized into JSON for visualization purposes.

python
# Convert to graph representation
vertices, edges = execution_info._to_graph()

# Serialize to JSON
graph_json = execution_info.graph_serialization()


## 2. Public API

### `class ExecutionInfo`
A class that contains the full details of the state of a run at any given point in time.

The class is designed to be used as a snapshot of state that can be used to display the state of the run, or to
create a graphical representation of the system.

#### `.__init__(self, request_forest, node_forest, stamper)`
Class constructor.

#### `.default(cls)`
Creates a new "empty" instance of the ExecutionInfo class with the default values.

#### `.create_new(cls)`
Creates a new empty instance of state variables with the provided executor configuration.

#### `.answer(self)`
Convenience method to access the answer of the run.

#### `.all_stamps(self)`
Convenience method to access all the stamps of the run.

#### `.insertion_requests(self)`
A convenience method to access all the insertion requests of the run.

#### `.graph_serialization(self)`
        Creates a string (JSON) representation of this info object designed to be used to construct a graph for this
        info object.

        Some important notes about its structure are outlined below:
        - The `nodes` key contains a list of all the nodes in the graph, represented as `Vertex` objects.
        - The `edges` key contains a list of all the edges in the graph, represented as `Edge` objects.
        - The `stamps` key contains an ease of use list of all the stamps associated with the run, represented as `Stamp` objects.

        - The "nodes" and "requests" key will be outlined with normal graph details like connections and identifiers in addition to a loose details object.
        - However, both will carry an addition param called "stamp" which is a timestamp style object.
        - They also will carry a "parent" param which is a recursive structure that allows you to traverse the graph in time.

        The current output_schema looks something like the following.
        json
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



---

## 3. Architectural Design

### 3.1 Core Design

- **State Management:** The `ExecutionInfo` class manages the state using `RequestForest` and `NodeForest` to track requests and nodes, respectively. The `StampManager` is used to handle timestamps.
- **Graph Representation:** The component uses `Vertex` and `Edge` classes to represent nodes and connections in a graph structure. This allows for a clear visualization of the system's execution flow.
- **Serialization:** The `RTJSONEncoder` is used to serialize the graph representation into JSON, supporting various custom types like `Vertex`, `Edge`, and `Stamp`.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **Profiling and Serialization:** The component relies on `Stamp` and `StampManager` from `railtracks.utils.profiling` and `Vertex` and `Edge` from `railtracks.utils.serialization.graph`.
- **Concurrency:** The `StampManager` uses locks to ensure thread-safe operations when creating stamps.

### 4.2 Performance & Limitations

- **Graph Complexity:** The complexity of the graph representation can grow with the number of nodes and requests, potentially impacting performance for very large datasets.

## 5. Related Files

### 5.1 Code Files

- [`node.py`](../packages/railtracks/src/railtracks/state/node.py): Defines the `NodeForest` and `LinkedNode` classes used for managing node states.
- [`request.py`](../packages/railtracks/src/railtracks/state/request.py): Contains the `RequestForest` and `RequestTemplate` classes for handling request states.
- [`serialize.py`](../packages/railtracks/src/railtracks/state/serialize.py): Provides serialization utilities, including the `RTJSONEncoder`.
- [`utils.py`](../packages/railtracks/src/railtracks/state/utils.py): Includes utility functions like `create_sub_state_info` for managing subsets of state information.
- [`profiling.py`](../packages/railtracks/src/railtracks/utils/profiling.py): Contains the `Stamp` and `StampManager` classes for timestamp management.
- [`graph.py`](../packages/railtracks/src/railtracks/utils/serialization/graph.py): Defines the `Vertex` and `Edge` classes for graph representation.

### 5.2 Related Component Files

- [`state_management.md`](../components/state_management.md): Provides an overview of state management components, including `ExecutionInfo`.

### 5.3 Related Feature Files

- [`state_management.md`](../features/state_management.md): Discusses the state management feature, which includes the `ExecutionInfo` component.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
