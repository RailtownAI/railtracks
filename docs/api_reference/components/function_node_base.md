# Function Node Base

The Function Node Base component provides a framework for creating dynamic function nodes, supporting both synchronous and asynchronous functions. It is designed to facilitate the conversion of function parameters to the required values and to manage the execution of these functions within a node-based architecture.

**Version:** 0.0.1

**Component Contact:** @developer_username

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The Function Node Base component is primarily used to create nodes that encapsulate function execution, allowing for both synchronous and asynchronous operations. This is particularly useful in scenarios where functions need to be dynamically integrated into a node-based processing pipeline.

### 1.1 Synchronous Function Node

The synchronous function node is used when the function to be executed is synchronous. This is important for operations that do not involve I/O-bound tasks or do not require concurrency.

python
class MySyncNode(SyncDynamicFunctionNode):
    @classmethod
    def func(cls, *args, **kwargs):
        return sum(args)

node = MySyncNode(1, 2, 3)
result = node.invoke()


### 1.2 Asynchronous Function Node

The asynchronous function node is used for functions that are I/O-bound or require concurrency, such as network requests or file I/O operations.

python
class MyAsyncNode(AsyncDynamicFunctionNode):
    @classmethod
    async def func(cls, *args, **kwargs):
        await asyncio.sleep(1)
        return sum(args)

node = MyAsyncNode(1, 2, 3)
result = await node.invoke()


## 2. Public API

### `class DynamicFunctionNode(Node[_TOutput], ABC, Generic[_P, _TOutput])`
A base class which contains logic around converting function parameters to the required value given by the function.
It also contains the framework for functionality of function nodes that can be built using the `from_function`
method.

NOTE: This class is not designed to be worked with directly. The classes SyncDynamicFunctionNode and
AsyncDynamicFunctionNode are the ones designed for consumption.

#### `.__init__(self, *args, **kwargs)`
Class constructor.

#### `.func(cls, *args, **kwargs)`
No docstring found.

#### `.name(cls)`
No docstring found.

#### `.tool_info(cls)`
No docstring found.

#### `.type_mapper(cls)`
No docstring found.

#### `.prepare_tool(cls, tool_parameters)`
No docstring found.


---
### `class SyncDynamicFunctionNode(DynamicFunctionNode[_P, _TOutput], ABC)`
A nearly complete class that expects a synchronous function to be provided in the `func` method.

The class' internals will handle the creation of the rest of the internals required for a node to operate.

You can override methods like name and tool_info to provide custom names and tool information. However,
do note that these overrides can cause unexpected behavior if not done according to what is expected in the parent
class as it uses a lot of the structures in its implementation of other functions.

#### `.func(cls, *args, **kwargs)`
The function that this node will call.
This function should be synchronous.

#### `.invoke(self)`
No docstring found.


---
### `class AsyncDynamicFunctionNode(DynamicFunctionNode[_P, _TOutput], ABC)`
A nearly complete class that expects an async function to be provided in the `func` method.

The class' internals will handle the creation of the rest of the internals required for a node to operate.

You can override methods like name and tool_info to provide custom names and tool information. However,
do note that these overrides can cause unexpected behavior if not done according to what is expected in the parent
class as it uses a lot of the structures in its implementation of other functions.

#### `.func(cls, *args, **kwargs)`
The async function that this node will call.

#### `.invoke(self)`
No docstring found.


---

## 3. Architectural Design

The Function Node Base component is designed with flexibility and extensibility in mind, allowing developers to create nodes that can execute both synchronous and asynchronous functions. The design leverages Python's type system and abstract base classes to enforce the implementation of required methods.

### 3.1 Dynamic Function Node

- **DynamicFunctionNode**: Serves as the base class for all function nodes. It provides the framework for parameter conversion and function execution.
  - **Design Consideration**: The class is abstract and not intended for direct instantiation. It requires subclasses to implement the `func`, `tool_info`, and `type_mapper` methods.

### 3.2 SyncDynamicFunctionNode

- **SyncDynamicFunctionNode**: Inherits from `DynamicFunctionNode` and is tailored for synchronous functions.
  - **Design Consideration**: Ensures that the function provided is synchronous and raises an error if a coroutine is returned.

### 3.3 AsyncDynamicFunctionNode

- **AsyncDynamicFunctionNode**: Inherits from `DynamicFunctionNode` and is tailored for asynchronous functions.
  - **Design Consideration**: Designed to handle asynchronous execution, leveraging Python's `asyncio` for concurrency.

## 4. Important Considerations

### 4.1 Parameter Conversion

- The `DynamicFunctionNode` uses a `TypeMapper` to convert function parameters to the appropriate types. This is crucial for ensuring that the function receives the correct input types.

### 4.2 Error Handling

- The `SyncDynamicFunctionNode` includes error handling to ensure that synchronous functions do not inadvertently return coroutines, which would lead to runtime errors.

## 5. Related Files

### 5.1 Code Files

- [`function_base.py`](../packages/railtracks/src/railtracks/nodes/concrete/function_base.py): Contains the implementation of the `DynamicFunctionNode`, `SyncDynamicFunctionNode`, and `AsyncDynamicFunctionNode`.

### 5.2 Related Component Files

- [`node_building.md`](../components/node_building.md): Provides documentation on building nodes within the system.

### 5.3 Related Feature Files

- [`node_management.md`](../features/node_management.md): Discusses the management and orchestration of nodes within the system.

### 5.4 External Dependencies

- [`typing_extensions`](https://pypi.org/project/typing-extensions/): Used for advanced type hinting features.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
