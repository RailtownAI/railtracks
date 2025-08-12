# Profiling

The Profiling component provides a system for creating and managing "stamps" that represent specific points in time, identified by a message and a step number. This is useful for tracking the sequence and timing of events within a system.

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

The Profiling component is primarily used to track and log specific events or actions within a system by creating "stamps." These stamps are useful for debugging, performance monitoring, and understanding the flow of execution in complex systems.

### 1.1 Creating a Stamp

Creating a stamp is essential for logging an event with a specific message and step number. This helps in tracking the sequence of operations.

python
from railtracks.utils.profiling import StampManager

manager = StampManager()
stamp = manager.create_stamp("Event started")


### 1.2 Using Stamp Creator

The stamp creator allows for the creation of multiple stamps with shared step values, which is useful for batch operations or grouped events.

python
stamp_creator = manager.stamp_creator()
stamp1 = stamp_creator("Batch event 1")
stamp2 = stamp_creator("Batch event 2")


## 2. Public API

### `class Stamp`
A simple dataclass that represents a stamp in time for the system.

Shared actions should have identical stamps, but they do not need to have identical time fields.


---
### `class StampManager`
A simple manager object that can be used to coordinate the creation of a stamps during the runtime of a system.

#### `.__init__(self)`
Creates a new instance of a `StampManager` object. It defaults the current step to 0.

#### `.create_stamp(self, message)`
Creates a new stamp with the given message.

Args:
    message (str): The message you would like the returned stamp to contain

Returns:
    Stamp: The newly created stamp with the next step value, your provided message and a timestamp determined
     at creation.

#### `.stamp_creator(self)`
Creates a method that can be used to create new stamps with shared step values.

This method guarantees the following properties:

- The stamp created by calling the method will have the timestamp of when the method was called.
- You can have different messages for each stamp created by the method.
- All stamps created by the method will share step values

Returns:
    (str) -> Stamp: A method that can be used to create new stamps with shared step values.

#### `.step_logs(self)`
Returns a copy of a dictionary containing a list of identifiers for each step that exist in the system.

#### `.all_stamps(self)`
Returns a list of the all the stamps that have been created in the system.


---

## 3. Architectural Design

### 3.1 Stamp and StampManager

- **Stamp Class**: Represents a point in time with a timestamp, step number, and identifier. It supports comparison based on time and step for ordering.
- **StampManager Class**: Manages the creation and storage of stamps. It ensures thread safety using locks and maintains a log of steps and their associated messages.

## 4. Important Considerations

### 4.1 Thread Safety

- The `StampManager` uses a threading lock to ensure that stamp creation is thread-safe. This is crucial in multi-threaded environments to prevent race conditions.

### 4.2 Performance

- The use of deep copies in `step_logs` and `all_stamps` properties ensures that the internal state is not modified externally, but it may have performance implications for large numbers of stamps.

## 5. Related Files

### 5.1 Code Files

- [`profiling.py`](../packages/railtracks/src/railtracks/utils/profiling.py): Contains the implementation of the `Stamp` and `StampManager` classes.

### 5.2 Related Feature Files

- [`logging_profiling.md`](../docs/features/logging_profiling.md): Documentation for the logging and profiling feature, which includes the use of the Profiling component.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
