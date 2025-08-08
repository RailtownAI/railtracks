# Pub/Sub Messaging

The Pub/Sub Messaging component is designed to facilitate asynchronous communication within the RailTracks system by implementing a publisher-subscriber pattern. This component allows different parts of the system to publish and subscribe to messages, enabling decoupled and efficient message handling.

**Version:** 0.0.1

**Component Contact:** @railtracks_dev

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The Pub/Sub Messaging component is primarily used for handling request completions within the RailTracks system. It supports publishing and subscribing to various types of messages, such as request success, failure, and creation messages. This component is crucial for enabling asynchronous communication and decoupling different parts of the system.

### 1.1 Publishing Messages

The primary use case is to publish messages related to request completions. This allows different parts of the system to react to these events without being tightly coupled.

python
from railtracks.pubsub.publisher import RTPublisher
from railtracks.pubsub.messages import RequestSuccess

async def main():
    publisher = RTPublisher()
    await publisher.start()
    message = RequestSuccess(request_id="123", node_state=some_node_state, result="Hello World")
    await publisher.publish(message)
    await publisher.shutdown()


### 1.2 Subscribing to Messages

Another key use case is subscribing to specific message types to perform actions based on the message content.

python
def handle_success(message):
    if isinstance(message, RequestSuccess):
        print(f"Request {message.request_id} succeeded with: {message.result}")

publisher.subscribe(handle_success, "success_handler")


## 2. Public API

### `class RequestCompletionMessage(ABC)`
The base class for all messages on the request completion system.

#### `.log_message(self)`
Converts the message to a string ready to be logged.


---
### `class RequestSuccess(RequestFinishedBase)`
A message that indicates the succseful completion of a request.

#### `.__init__(self)`
Class constructor.

#### `.log_message(self)`
No docstring found.


---
### `class RequestFailure(RequestFinishedBase)`
A message that indicates a failure in the request execution.

#### `.__init__(self)`
Class constructor.

#### `.log_message(self)`
No docstring found.


---
### `class RequestCreationFailure(RequestFinishedBase)`
A special class for situations where the creation of a new request fails before it was ever able to run.

#### `.__init__(self)`
Class constructor.

#### `.log_message(self)`
No docstring found.


---
### `class RequestCreation(RequestCompletionMessage)`
A message that describes the creation of a new request in the system.

#### `.__init__(self)`
Class constructor.


---
### `class FatalFailure(RequestCompletionMessage)`
A message that indicates an irrecoverable failure in the request completion system.

#### `.__init__(self)`
Class constructor.


---
### `class Streaming(RequestCompletionMessage)`
A message that indicates a streaming operation in the request completion system.

#### `.__init__(self)`
Class constructor.


---
### `def output_mapping(result)`
Maps the result of a RequestCompletionMessage to its final output.


---
### `def stream_subscriber(sub_callback)`
Converts the basic streamer callback into a broadcast_callback handler designed to take in `RequestCompletionMessage`


---

## 3. Architectural Design

The Pub/Sub Messaging component is designed around the publisher-subscriber pattern, which decouples message producers from consumers. This design allows for scalable and maintainable communication within the system.

### 3.1 Core Components

- **Messages (`messages.py`)**: Defines various message types that can be published and subscribed to, such as `RequestSuccess`, `RequestFailure`, and `Streaming`.
- **Publisher (`publisher.py`)**: Manages the distribution of messages to subscribers. It uses asynchronous operations to ensure non-blocking message handling.
- **Subscriber (`_subscriber.py`)**: Provides utilities for creating subscribers that can handle specific message types.
- **Utilities (`utils.py`)**: Contains helper functions like `output_mapping` to process message results.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- Ensure that the `railtracks` package is installed and properly configured.
- The component relies on `asyncio` for asynchronous operations.

### 4.2 Performance & Limitations

- The system is designed to handle a high volume of messages efficiently.
- Ensure that subscribers are optimized to prevent bottlenecks.

### 4.3 Debugging & Observability

- Enable debug logging to trace message flows.
- Use the `log_message()` method in messages for standardized logging.

## 5. Related Files

### 5.1 Code Files

- [`_subscriber.py`](../packages/railtracks/src/railtracks/pubsub/_subscriber.py): Contains subscriber utilities.
- [`messages.py`](../packages/railtracks/src/railtracks/pubsub/messages.py): Defines message types.
- [`publisher.py`](../packages/railtracks/src/railtracks/pubsub/publisher.py): Implements the publisher.
- [`utils.py`](../packages/railtracks/src/railtracks/pubsub/utils.py): Provides utility functions.

### 5.2 Related Component Files

- [`context_management.md`](../components/context_management.md): Discusses context management related to message handling.

### 5.3 Related Feature Files

- [`task_execution.md`](../features/task_execution.md): Describes task execution features that integrate with the Pub/Sub system.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.

