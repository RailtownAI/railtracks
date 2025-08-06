# Request Management

The Request Management component is responsible for managing a system of requests and their relationships, providing mechanisms to create, update, and query requests within the system.

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

The Request Management component is designed to handle the lifecycle of requests within a system. It allows for the creation, updating, and querying of requests, which can be linked to form a directed graph of operations. This is particularly useful in systems where operations are dependent on the completion of previous tasks.

### 1.1 Creating a Request

Creating a request is a fundamental operation that initializes a new request in the system.

python
from railtracks.state.request import RequestForest, Stamp

request_forest = RequestForest()
identifier = request_forest.create(
    identifier="unique_id",
    source_id=None,
    sink_id="sink_node",
    input_args=(),
    input_kwargs={},
    stamp=Stamp()
)


### 1.2 Updating a Request

Updating a request allows you to modify the output of an existing request, marking it as completed or failed.

python
request_forest.update(
    identifier="unique_id",
    output="result_data",
    stamp=Stamp()
)


## 2. Public API

### `class RequestTemplate(AbstractLinkedObject)`
A simple object containing details about a request in the system.

#### `.to_edge(self)`
Converts the request template to an edge representation.

#### `.closed(self)`
If the request has an output it is closed

#### `.is_insertion(self)`
If the request is an insertion request it will return True.

#### `.status(self)`
Gets the current status of the request.

#### `.get_all_parents(self)`
Recursely collects all the parents for the request.

#### `.get_terminal_parent(self)`
Returns the terminal parent of the request.

If this request is the parent then it will return itself.

#### `.duration_detail(self)`
Returns the difference in time between the parent and the current request stamped time.

#### `.generate_id(cls)`
Generates a new unique identifier for the request. This is suitable for use as a request identifier.

#### `.downstream(cls, requests, source_id)`
Collects the requests one level downstream from the provided source_id.

#### `.upstream(cls, requests, sink_id)`
Collects the requests one level upstream from the provided sink_id.

#### `.all_downstream(cls, requests, source_id)`
Collects all the downstream requests from the provided source_id.

#### `.open_tails(cls, requests, source_id)`
Traverses down the provided tree to find all the open tails.

Open Tail: is defined as any node which currently holds an open request and does not have any open ones beneath
it.

#### `.children_complete(cls, requests, source_node_id)`
Checks if all the downstream requests of a given parent node are complete. If so returns True.
 Otherwise, returns False.


---
### `class RequestForest(Forest[RequestTemplate])`
No docstring found.

#### `.__init__(self, request_heap)`
Creates a new instance of a request heap with no objects present.

#### `.to_edges(self)`
Converts the current heap into a list of `Edge` objects.

#### `.create(self, identifier, source_id, sink_id, input_args, input_kwargs, stamp)`
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

#### `.update(self, identifier, output, stamp)`
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

#### `.children(self, parent_id)`
Finds all the children of the provided parent_id.

#### `.generate_graph(cls, heap)`
Generates a dictionary representation contain the edges in the graph. The key of the dictionary is the source
and the value is a list of tuples where the first element is the sink_id and the second element is the request        id.
Complexity: O(n) where n is the number of identifiers in the heap.

Args:
    heap (Dict[str, RequestTemplate]): The heap of requests to generate the graph from.

Returns:
    Dict[str, List[Tuple[str, str]]]: The graph representation of the heap.

#### `.get_request_from_child_id(self, child_id)`
Gets the request where this child_id is the sink_id of the request.

Via the invariants of the system. There must only be 1 request that satisfies the above requirement.

#### `.open_tails(self)`
Collects the current open tails in the heap. See `RequestTemplate.open_tails` for more information.

#### `.children_requests_complete(self, parent_node_id)`
Checks if all the downstream requests (one level down) if the given parent node are complete. If they are
 then it will return the request id of the parent node. Otherwise, it will return None.

Note that you are providing the node_id of the parent node and downstream requests of that node is defined
 as any of the requests which have the matching parent_node.

Args:
    parent_node_id (str): The parent node id

Returns:
    The request_id string of the parent node if all the children are complete otherwise None.

#### `.insertion_request(self)`
Collects a list of all the insertion requests in the heap.

They will be returned in the order that they were created.

#### `.answer(self)`
Collects the answer to the insertion request.

The behavior of the function can be split into two cases:

1. There is either 1 or 0 insertion requests present:
 - In this case, it will return the output of the insertion request if it exists, otherwise None

2. There is more than 1 insertion request:
 - Returns an ordered list of outputs of all the insertion requests. If one has not yet completed, it will
   return None in that index.


---

## 3. Architectural Design

### 3.1 Request Template

- **Request Representation:** Each request is represented by a `RequestTemplate` object, which includes details such as source and sink identifiers, input and output data, and parent-child relationships.
- **Graph Structure:** Requests can be linked to form a directed graph, allowing for complex workflows where requests depend on the completion of others.

### 3.2 Request Forest

- **Heap Management:** The `RequestForest` class manages a collection of requests, stored in a heap. It provides thread-safe operations to create, update, and query requests.
- **Concurrency Considerations:** The use of locks ensures that operations on the request heap are thread-safe, preventing race conditions.

## 4. Important Considerations

### 4.1 Concurrency and Thread Safety

- **Locking Mechanism:** The `RequestForest` class uses a locking mechanism to ensure that operations on the request heap are thread-safe. This is crucial for preventing race conditions in a multi-threaded environment.

### 4.2 Error Handling

- **Custom Exceptions:** The component defines custom exceptions such as `RequestDoesNotExistError` and `RequestAlreadyExistsError` to handle specific error cases related to request management.

## 5. Related Files

### 5.1 Code Files

- [`../state/request.py`](../state/request.py): Contains the implementation of the Request Management component, including the `RequestTemplate` and `RequestForest` classes.

### 5.2 Related Component Files

- [`../components/state_management.md`](../components/state_management.md): Provides an overview of the state management system, of which the Request Management component is a part.

### 5.3 Related Feature Files

- [`../features/state_management.md`](../features/state_management.md): Describes the state management features and how they integrate with the Request Management component.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
