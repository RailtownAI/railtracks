# 📡 PubSub (Publisher-Subscriber) Documentation
<link rel="stylesheet" href="/system_internals/css/class_diagram.css">
<script src="/system_internals/js/class_diagram.js"></script>
## 🔍 Overview

The PubSub (Publisher-Subscriber) system is a messaging pattern that allows different parts of the **RailTracks** system to communicate asynchronously. Think of it like a radio station: publishers broadcast messages (like radio shows), and subscribers listen for messages they're interested in (like tuning into specific stations).

## 🤔 What is PubSub?

PubSub is a communication pattern where:

- **Publishers** send messages without knowing who will receive them
- **Subscribers** listen for messages they care about without knowing who sent them
- A **message broker** (in our case, the Publisher class) handles the routing

This creates loose coupling between components - they don't need to know about each other directly.

## 📞 What are Callbacks?

A **callback** is a function that gets called automatically when something happens. In the context of PubSub:

- You give the system a function (the callback)
- The system calls your function when a relevant message arrives
- Your function receives the message as a parameter

Example:
```python
def my_callback(message):
    print(f"Received: {message}")

# This callback will be called whenever a message is published
```

## 🧩 Core Components

### 1. 📨 Messages (`messages.py`)

Messages are the data structures that flow through the PubSub system. All messages inherit from `RequestCompletionMessage`:

#### 🏗️ Base Message Class
- **`RequestCompletionMessage`**: The foundation for all messages in the system
  - Has a `log_message()` method for debugging

#### 🔄 Request Lifecycle Messages
- **`RequestCreation`**: Sent when a new request is created
    - Contains: current node ID, new request ID, execution mode, node type, and arguments
- **`RequestSuccess`**: Sent when a request completes successfully
    - Contains: request ID, node state, and the result
- **`RequestFailure`**: Sent when a request fails during execution
    - Contains: request ID, node state, and the error
- **`RequestCreationFailure`**: Sent when request creation itself fails
    - Contains: request ID and the error

#### ⚡ Special Messages
- **`FatalFailure`**: Indicates an irrecoverable system failure
- **`Streaming`**: Used for streaming data during execution
    - Contains: the streamed object and node ID

### 2. 📢 Publisher (`publisher.py`)

The Publisher is the central message broker that manages message distribution.

#### 🚀 Basic Publisher Features
- **Asynchronous**: Uses `asyncio` for non-blocking operations
- **Ordered**: Messages are processed in the order they arrive
- **Thread-safe**: Multiple components can publish simultaneously

#### 🔑 Key Methods

**🎬 Starting and Stopping:**
```python
publisher = Publisher()
await publisher.start()  # Start the message processing loop
await publisher.shutdown()  # Stop and cleanup
```

**📤 Publishing Messages:**
```python
await publisher.publish(message)  # Send a message to all subscribers
```

**📥 Subscribing:**
```python
def my_callback(message):
    print(f"Got message: {message}")

subscriber_id = publisher.subscribe(my_callback, name="my_subscriber")
```

**🚫 Unsubscribing:**
```python
publisher.unsubscribe(subscriber_id)  # Remove a specific broadcast_callback
```

**🔗 Workflow Example:**
```python
import asyncio
from railtracks.pubsub.publisher import Publisher

def callback(message: str):
    """
    A simple callback function that processes incoming messages.
    """
    print(f"Received message: {message}")

publisher = Publisher()
await publisher.start()  # Start the publisher
subscriber_id = publisher.subscribe(callback, name="example_subscriber")
await publisher.publish("Hello, World!")  # Publish a message

await asyncio.sleep(1)  # Wait for the message to be processed
await publisher.shutdown()  # Stop the publisher
```
#### 🎯 Advanced Features

**👂 Listeners:**
Listeners wait for a specific message that matches criteria:
```python
# Wait for the first message that matches the filter
result = await publisher.listener(
    message_filter=lambda msg: isinstance(msg, RequestSuccess),
    result_mapping=lambda msg: msg.result,
    listener_name="success_listener"
)
```

**🔒 Context Manager Support:**
```python
async with Publisher() as pub:
    await pub.publish(message)
# Publisher automatically shuts down when exiting the context
```

### 3. 👥 Subscriber (`subscriber.py`)
<div class="class-diagram" id="subscriber-diagram" data-diagram='{
  "classes": [
    {
      "id": "subscriber",
      "name": "Subscriber",
      "attributes": [
        {"name": "callback", "type": "Callable[[RequestCompletionMessage], None]", "visibility": "public"},
        {"name": "name", "type": "str", "visibility": "public"},
        {"name": "id", "type": "str", "visibility": "public"}
      ],
      "methods": [
        {"name": "__init__", "parameters": "execution_modes: Dict[ExecutionConfigurations, TaskExecutionStrategy]", "visibility": "public"},
        {"name": "trigger", "parameters": "message: RequestCompletionMessage", "returnType": "void", "visibility": "public"}
      ]
    }
  ]
}'></div>
Contains utilities for creating specialized subscribers.

#### 🌊 Stream Subscriber
Converts streaming callbacks into proper message subscribers:
```python
def handle_stream_data(data):
    print(f"Streaming: {data}")

subscriber = stream_subscriber(handle_stream_data)
publisher.subscribe(subscriber)
```

### 4. 🛠️ Utilities (`utils.py`)

Helper functions for working with messages.

#### 🗺️ Output Mapping
Converts message results into their final outputs or raises errors:
```python
try:
    result = output_mapping(message)
    print(f"Success: {result}")
except Exception as error:
    print(f"Failed: {error}")
```

## 🎯 RailTracks Publisher (RTPublisher)

`RTPublisher` is a specialized publisher for the RailTracks system that:

- Automatically logs all messages for debugging
- Handles RailTracks specific message types
- Provides built-in error logging with stack traces

```python
publisher = RTPublisher()
await publisher.start()
```

## 🎨 Common Usage Patterns

### 1. 📝 Basic Message Publishing
```python
# Create and start publisher
async with RTPublisher() as publisher:
    # Create a message
    message = RequestSuccess(
        request_id="123",
        node_state=some_node_state,
        result="Hello World"
    )
    
    # Publish it
    await publisher.publish(message)
```

### 2. 🎯 Subscribing to Specific Message Types
```python
def handle_success(message):
    if isinstance(message, RequestSuccess):
        print(f"Request {message.request_id} succeeded with: {message.result}")

def handle_failure(message):
    if isinstance(message, RequestFailure):
        print(f"Request {message.request_id} failed: {message.error}")

publisher.subscribe(handle_success, "success_handler")
publisher.subscribe(handle_failure, "failure_handler")
```

### 3. ⏰ Waiting for Specific Results
```python
# Wait for a specific request to complete
result = await publisher.listener(
    message_filter=lambda msg: (
        isinstance(msg, (RequestSuccess, RequestFailure)) and 
        msg.request_id == "my_request_123"
    ),
    result_mapping=output_mapping,  # Convert to final result or raise error
    listener_name="request_waiter"
)
```

### 4. 🌊 Streaming Data
```python
def process_stream(data):
    # Process each piece of streaming data
    print(f"Processing: {data}")

# Subscribe to streaming messages
stream_handler = stream_subscriber(process_stream)
publisher.subscribe(stream_handler, "stream_processor")
```

## ⚠️ Error Handling

The PubSub system handles errors gracefully:

1. **Subscriber Errors**: If a subscriber's callback fails, it's logged but doesn't affect other subscribers
2. **Publisher Errors**: Fatal errors are communicated through `FatalFailure` messages
3. **Request Errors**: Both creation and execution failures have specific message types

## ✅ Best Practices

1. **Always use descriptive names** for subscribers to aid debugging
2. **Handle errors in your callbacks** - don't let them crash the system
3. **Use context managers** when possible for automatic cleanup
4. **Filter messages efficiently** - check message types early in your callbacks
5. **Unsubscribe when done** to prevent memory leaks
6. **Use listeners for one-time responses** instead of persistent subscribers

## 🧵 Thread Safety and Async Considerations

- The Publisher uses `asyncio.Queue` for thread-safe message handling
- All operations are asynchronous - always use `await`
- Messages are processed sequentially to maintain order
- The system gracefully handles shutdown during active operations

## 🐛 Debugging Tips

1. **Enable debug logging** to see all message flows
2. **Use meaningful subscriber names** for easier log interpretation
3. **Check the `log_message()` output** for standardized message descriptions
4. **Monitor the publisher's running state** with `is_running()`
5. **Use the built-in logging subscriber** in RCPublisher for automatic message logging

This PubSub system provides a robust foundation for decoupled communication throughout the Request Completion framework, allowing components to interact without tight coupling while maintaining reliability and observability.