# State Management

The `Forest` component is designed to manage a collection of linked objects, tracking their history and state over time. It provides a mechanism to record and access the history of immutable objects, allowing developers to manage state changes efficiently.

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

The `Forest` component is primarily used to manage and track the history of objects by linking them together based on identifiers. This allows developers to access any point in the object's history, making it useful for applications that require state management and historical data tracking.

### 1.1 Managing Object History

The primary use case of the `Forest` component is to manage the history of objects. By linking objects with the same identifier, developers can create a timeline of immutable objects that can be accessed at any point in time.

python
from railtracks.state.forest import Forest, AbstractLinkedObject

# Define a custom linked object
class MyLinkedObject(AbstractLinkedObject):
    pass

# Initialize a Forest
forest = Forest()

# Add objects to the forest
obj1 = MyLinkedObject(identifier="obj1", stamp=Stamp(step=1), parent=None)
forest._update_heap(obj1)

# Access the most recent object
recent_obj = forest["obj1"]


### 1.2 Time Travel for Objects

Another important use case is the ability to revert objects to a previous state using the `time_machine` method. This allows developers to "time travel" objects to a specific point in their history.

python
# Revert objects to a previous state
forest.time_machine(step=1, item_list=["obj1"])


## 2. Public API

### `class Forest(Generic[T])`
A general base class for any heap object. These heap objects have a non-intuitive structure. A common use case of
a type like this is used to record history of some object. By linking together objects with the same identifier, you
can create a history of immutable objects that can be accessed at any point in time. You can also build out any of
your own desired functionality of the object by subclassing `Forest`.

The general principle of the object is you can add any subclass of `AbstractLinkedObject` to the heap. The heap will
track any object with identical identifiers as connected objects. Any object which you add that already exists in
the heap (and by that I mean an object with the same identifier) must have a parent in the graph that matches that
object. Once you have added that new object it is now the object that you can access from the heap. Conveniently
because all `T` are immutable, you can pass around the objects without worry of pass by reference bugs.

#### `.__init__(self, heap)`
Class constructor.

#### `.heap(self)`
Returns a passed by value dictionary of all the data in the heap.

NOTE: You can do whatever you please with this object, and it will not affect the inner workings of the object.

#### `.full_data(self, at_step)`
Returns a passed by value list of all the data in the heap.

NOTE: You can do whatever you please with this object, and it will not affect the inner workings of the object.

#### `.time_machine(self, step, item_list)`
This function mutates the state of self such that all items you have provided are returned to state at the given
step. If you have not provided any items it will be assumed that you want the entire heap to be returned to the
given step.

Note that it will include all items with the given step and less (it is inclusive of the step).

If none of the items with the given ID are less than or equal to the given step, then the item will be removed.

Args:
    step (int): The step to return the items to (inclusive of that step). If none then return the current state.
    item_list (Optional[List[str]]): The list of identifiers to return to the given step. If None, then all items
        will be returned to the given step. Note an empty list will mean that nothing will happen


---

## 3. Architectural Design

The `Forest` component is designed to manage a collection of linked objects, each represented by the `AbstractLinkedObject` class. The core philosophy is to maintain immutability and provide a mechanism to track object history efficiently.

### 3.1 Core Design Principles

- **Immutability:** All objects managed by the `Forest` are immutable, ensuring that state changes do not lead to unintended side effects.
- **Thread Safety:** The component uses a reentrant lock (`RLock`) to ensure thread-safe operations when updating the heap.
- **History Tracking:** By linking objects with the same identifier, the component creates a history of objects that can be accessed at any point in time.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- The component relies on the `Stamp` class from `railtracks.utils.profiling` to manage timestamps for objects.

### 4.2 Performance & Limitations

- The component is designed to handle a large number of objects, but performance may degrade with extremely large datasets due to the recursive nature of the `_create_full_data_from_heap` method.

### 4.3 State Management & Concurrency

- The component uses a reentrant lock to manage concurrent access, ensuring that updates to the heap are thread-safe.

## 5. Related Files

### 5.1 Code Files

- [`forest.py`](../packages/railtracks/src/railtracks/state/forest.py): Contains the implementation of the `Forest` component and related classes.

### 5.2 Related Component Files

- [`profiling.py`](../packages/railtracks/src/railtracks/utils/profiling.py): Provides the `Stamp` class used for managing timestamps in the `Forest` component.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
