# State Utilities

The State Utilities component provides functionality to create a subset of node and request data structures based on specified parent IDs. This is essential for managing and manipulating subsets of data within larger node and request heaps, allowing for efficient data processing and analysis.

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

The primary purpose of the State Utilities component is to filter and create subsets of node and request data structures. This is particularly useful in scenarios where only a specific portion of the data is needed for processing, thereby optimizing performance and resource usage.

### 1.1 Creating Sub-State Information

The `create_sub_state_info` function is the core utility provided by this component. It allows developers to create a subset of the original node and request heaps based on specified parent IDs. This function is crucial for tasks that require focused data manipulation without the overhead of processing the entire dataset.

python
from railtracks.state.utils import create_sub_state_info

# Example usage
node_heap = {...}  # Dictionary of LinkedNode objects
request_heap = {...}  # Dictionary of RequestTemplate objects
parent_ids = "parent_id_1"

node_forest, request_forest = create_sub_state_info(node_heap, request_heap, parent_ids)


## 2. Public API

### `def create_sub_state_info(node_heap, request_heap, parent_ids)`
Creates a subset of the original heaps to include only the nodes and requests.

The parent_ids will identify how the filtering should occur.
- If a single ID is provided, it will be used as the root to find all downstream requests.
- If a list of IDs is provided, it will find all requests downstream of each ID in the list.
- If you provide multiple IDs on the same chain the behavior is undetermined.


---

## 3. Architectural Design

The design of the State Utilities component is centered around the efficient creation of sub-state information from larger data structures. The component leverages the `LinkedNode` and `RequestTemplate` classes to represent nodes and requests, respectively.

### 3.1 Design Considerations

- **Data Filtering:** The component filters nodes and requests based on parent IDs, allowing for targeted data processing.
- **Efficiency:** By creating subsets of data, the component reduces the computational load and improves performance.
- **Flexibility:** The function can handle both single and multiple parent IDs, providing flexibility in data selection.

## 4. Important Considerations

### 4.1 Implementation Details

- **Node and Request Classes:** The component relies on the `LinkedNode` and `RequestTemplate` classes, which are defined in the [node.py](../packages/railtracks/src/railtracks/state/node.py) and [request.py](../packages/railtracks/src/railtracks/state/request.py) files, respectively.
- **Data Integrity:** The function ensures that there are no duplicate entries in the resulting subsets, maintaining data integrity.

## 5. Related Files

### 5.1 Code Files

- [`utils.py`](../packages/railtracks/src/railtracks/state/utils.py): Contains the implementation of the `create_sub_state_info` function.

### 5.2 Related Component Files

- [`state_management.md`](../components/state_management.md): Provides additional context and documentation on state management within the project.

### 5.3 Related Feature Files

- [`state_management.md`](../features/state_management.md): Details the features related to state management, including the use of state utilities.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
