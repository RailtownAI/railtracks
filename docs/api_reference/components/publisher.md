# Publisher

The `Publisher` component implements a simple publish-subscribe pattern using asynchronous programming, allowing subscribers to receive messages in an orderly fashion.

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

The `Publisher` component is designed to facilitate asynchronous message broadcasting to multiple subscribers. It ensures that messages are processed in the order they are received and provides mechanisms for managing subscriber callbacks.

### 1.1 Publish and Subscribe

The primary use case of the `Publisher` is to allow subscribers to register callback functions that are triggered when a message is published.

python
import asyncio
from railtracks.utils.publisher import Publisher

async def my_callback(message):
    print(f"Received: {message}")

async def main():
    async with Publisher() as publisher:
        publisher.subscribe(my_callback)
        await publisher.publish("Hello, World!")

asyncio.run(main())


### 1.2 Listener for Specific Messages

Another use case is to create a listener that waits for a specific message that matches a given filter.

python
async def message_filter(message):
    return message == "Target Message"

async def main():
    async with Publisher() as publisher:
        result = await publisher.listener(message_filter)
        print(f"Filtered Message: {result}")

asyncio.run(main())


## 2. Public API

### `class Subscriber(Generic[_T])`
A simple wrapper class of a callback function.

#### `.__init__(self, callback, name)`
Class constructor.

#### `.trigger(self, message)`
Trigger this broadcast_callback with the given message.


---
### `class Publisher(Generic[_T])`
A simple publisher object with some basic functionality to publish and suvbscribe to messages.

Note a couple of things:
- Message will be handled in the order they came in (no jumping the line)
- If you add a broadcast_callback during the operation it will handle any new messages that come in after the subscription
    took place
- Calling the shutdown method will kill the publisher forever. You will have to make a new one after.

#### `.__init__(self)`
Class constructor.

#### `.start(self)`
No docstring found.

#### `.publish(self, message)`
Publish a message the publisher. This will trigger all subscribers to receive the message.

Args:
    message: The message you would like to publish.

#### `.subscribe(self, callback, name)`
Subscribe the publisher so whenever we receive a message the callback will be triggered.

Args:
    callback: The callback function that will be triggered when a message is published.
    name: Optional name for the broadcast_callback, mainly used for debugging.

Returns:
    str: A unique identifier for the broadcast_callback. You can use this key to unsubscribe later.

#### `.unsubscribe(self, identifier)`
Unsubscribe the publisher so the given broadcast_callback will no longer receive messages.

Args:
    identifier: The unique identifier of the broadcast_callback to remove.

Raises:
    KeyError: If no broadcast_callback with the given identifier exists.

#### `.listener(self, message_filter, result_mapping, listener_name)`
Creates a special listener object that will wait for the first message that matches the given filter.

After receiving the message it will run the result_mapping function on the message and return the result, and
kill the broadcast_callback.

Args:
    message_filter: A function that takes a message and returns True if the message should be returned.
    result_mapping: A function that maps the message into a final result.
    listener_name: Optional name for the listener, mainly used for debugging.

#### `.shutdown(self)`
Shutdowns the publisher and halts the listener loop.

Note that this will work slowly, as it will wait for the current messages in the queue to be processed before
shutting down.

#### `.is_running(self)`
Check if the publisher is currently running.

Returns:
    bool: True if the publisher is running, False otherwise.


---

## 3. Architectural Design

### 3.1 Core Design

- **Asynchronous Processing:** The `Publisher` uses Python's `asyncio` library to handle asynchronous message processing, ensuring non-blocking operations.
- **Subscriber Management:** Subscribers are managed through the `Subscriber` class, which wraps callback functions and provides a unique identifier for each subscriber.
- **Message Queue:** An internal `asyncio.Queue` is used to store messages, ensuring they are processed in the order they are received.

### 3.2 Key Design Decisions

- **Extendability:** The `Subscriber` class is designed to be extendable, allowing for future enhancements without breaking existing functionality.
- **Error Handling:** Errors in subscriber callbacks are logged but do not interrupt the message processing loop, ensuring robustness.

## 4. Important Considerations

### 4.1 Implementation Details

- **Concurrency:** The `Publisher` is not thread-safe and should be used within a single event loop.
- **Shutdown Behavior:** The `shutdown` method waits for all messages in the queue to be processed before stopping the publisher, which may introduce delays.

## 5. Related Files

### 5.1 Code Files

- [`../utils/publisher.py`](../utils/publisher.py): Contains the implementation of the `Publisher` and `Subscriber` classes.

### 5.2 Related Component Files

- [`../components/pubsub_messaging.md`](../components/pubsub_messaging.md): Provides an overview of the publish-subscribe messaging system.

### 5.3 Related Feature Files

- [`../features/task_execution.md`](../features/task_execution.md): Describes how the `Publisher` integrates with task execution features.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
