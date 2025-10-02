# Extending the HIL Abstract Class

The Human-in-the-Loop (HIL) interface allows you to create custom communication channels between your Railtracks agents and users. This guide shows you how to implement your own HIL interface by extending the `HIL` abstract class.

## Overview

The `HIL` abstract class defines a contract for bidirectional communication with users. Any implementation must provide four key methods:

- `connect()` - Initialize the communication channel
- `disconnect()` - Clean up resources
- `send_message()` - Send messages to the user
- `receive_message()` - Receive input from the user

## The HIL Interface

```python

```

## Implementation Guide

### 1. Basic Structure

Start by creating a class that inherits from `HIL`:

```python
import asyncio
from railtracks.human_in_the_loop import HIL, HILMessage

class MyCustomHIL(HIL):
    def __init__(self, **config):
        # Initialize your configuration
        self.is_connected = False
        self.input_queue = asyncio.Queue()
        self.output_queue = asyncio.Queue()
        self.shutdown_event = asyncio.Event()
```

### 2. Implement connect()

The `connect()` method should initialize all resources needed for communication:

```python
async def connect(self) -> None:
    """
    Initialize the communication channel.
    
    Examples of what to do here:
    - Start a web server (FastAPI, Flask, etc.)
    - Open a WebSocket connection
    - Initialize messaging service clients (Slack, Discord, etc.)
    - Open file handles or database connections
    """
    # Example: Start a server
    self.server = await self._start_server()
    self.is_connected = True
    
    # Optionally open a browser or notify the user
    if self.auto_open:
        webbrowser.open(f"http://{self.host}:{self.port}")
```

**Key considerations:**

- Set a flag like `self.is_connected = True` to track state
- Raise appropriate exceptions if initialization fails (e.g., `ConnectionError`)
- Make it idempotent when possible

### 3. Implement disconnect()

The `disconnect()` method should clean up all resources:

```python
async def disconnect(self) -> None:
    """
    Clean up all resources.
    
    Should be safe to call multiple times.
    """
    self.is_connected = False
    self.shutdown_event.set()
    
    # Close servers, connections, etc.
    if hasattr(self, 'server') and self.server:
        await self.server.shutdown()
    
    # Cancel any pending tasks
    if hasattr(self, 'server_task') and self.server_task:
        self.server_task.cancel()
```

**Key considerations:**

- Always set `self.is_connected = False` first
- Handle cleanup gracefully even if resources weren't fully initialized
- Don't raise exceptions - log errors instead

### 4. Implement send_message()

This method sends messages from the agent to the user:

```python
async def send_message(
    self, content: HILMessage, timeout: float | None = None
) -> bool:
    """
    Send a message to the user.
    
    Returns:
        True if successful, False otherwise
    """
    if not self.is_connected:
        logger.warning("Cannot send message - not connected")
        return False
    
    try:
        # Prepare your message format
        message = {
            "type": "agent_response",
            "content": content.content,
            "metadata": content.metadata
        }
        
        # Send through your communication channel
        # (e.g., queue for SSE, WebSocket send, HTTP POST, etc.)
        await asyncio.wait_for(
            self.output_queue.put(message),
            timeout=timeout
        )
        return True
        
    except asyncio.QueueFull:
        logger.warning("Output queue is full")
        return False
    except asyncio.TimeoutError:
        logger.warning("Timeout while sending message")
        return False
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False
```

**Key considerations:**

- Check `self.is_connected` before attempting to send
- Return `False` on any failure, don't raise exceptions
- Use `asyncio.wait_for()` to respect the timeout
- Handle queue full conditions gracefully

### 5. Implement receive_message()

This method receives input from the user:

```python
async def receive_message(
    self, timeout: float | None = None
) -> HILMessage | None:
    """
    Wait for user input.
    
    Returns:
        HILMessage if received, None on timeout or disconnection
    """
    if not self.is_connected:
        return None
    
    # Create tasks for input and shutdown
    input_task = asyncio.create_task(self.input_queue.get())
    shutdown_task = asyncio.create_task(self.shutdown_event.wait())
    
    try:
        done, pending = await asyncio.wait(
            [input_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
            timeout=timeout
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
        
        # Check which task completed
        if input_task in done:
            message = input_task.result()
            return message
        
        # Shutdown or timeout
        return None
        
    except asyncio.TimeoutError:
        input_task.cancel()
        shutdown_task.cancel()
        return None
    except asyncio.CancelledError:
        return None
```

**Key considerations:**

- Return `None` on timeout, disconnection, or shutdown
- Use `asyncio.wait()` to handle multiple events (input + shutdown)
- Always cancel pending tasks to avoid resource leaks
- Handle `asyncio.TimeoutError` and `asyncio.CancelledError`

## Complete Examples

### Example 1: Simple Console HIL

A basic console-based implementation:

```python
import asyncio
from railtracks.human_in_the_loop import HIL, HILMessage

class ConsoleHIL(HIL):
    def __init__(self):
        self.is_connected = False
        self.shutdown_event = asyncio.Event()
    
    async def connect(self) -> None:
        self.is_connected = True
        print("Console HIL connected. Type your messages below.")
    
    async def disconnect(self) -> None:
        self.is_connected = False
        self.shutdown_event.set()
        print("\nConsole HIL disconnected.")
    
    async def send_message(
        self, content: HILMessage, timeout: float | None = None
    ) -> bool:
        if not self.is_connected:
            return False
        print(f"\nAgent: {content.content}")
        return True
    
    async def receive_message(
        self, timeout: float | None = None
    ) -> HILMessage | None:
        if not self.is_connected:
            return None
        
        # Run input() in executor to avoid blocking
        loop = asyncio.get_running_loop()
        
        input_task = asyncio.create_task(
            loop.run_in_executor(None, input, "You: ")
        )
        shutdown_task = asyncio.create_task(self.shutdown_event.wait())
        
        try:
            done, pending = await asyncio.wait(
                [input_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=timeout
            )
            
            for task in pending:
                task.cancel()
            
            if input_task in done:
                user_input = input_task.result()
                return HILMessage(content=user_input)
            
            return None
            
        except asyncio.TimeoutError:
            input_task.cancel()
            shutdown_task.cancel()
            return None

# Usage
async def main():
    hil = ConsoleHIL()
    await hil.connect()
    
    await hil.send_message(HILMessage(content="Hello! How can I help you?"))
    
    user_msg = await hil.receive_message(timeout=30.0)
    if user_msg:
        print(f"Received: {user_msg.content}")
    
    await hil.disconnect()

asyncio.run(main())
```

### Example 2: Web-Based HIL with FastAPI

A more sophisticated implementation using FastAPI and Server-Sent Events (based on the ChatUI implementation):

```python
import asyncio
import json
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from railtracks.human_in_the_loop import HIL, HILMessage

class UserMessage(BaseModel):
    message: str
    timestamp: Optional[str] = None

class WebHIL(HIL):
    def __init__(self, port: int = 8000, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        
        # Message queues
        self.sse_queue = asyncio.Queue(maxsize=100)  # To browser
        self.user_input_queue = asyncio.Queue(maxsize=100)  # From browser
        
        self.shutdown_event = asyncio.Event()
        self.is_connected = False
        
        # Create FastAPI app
        self.app = self._create_app()
        self.server = None
        self.server_task = None
    
    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(title="Web HIL")
        
        @app.get("/", response_class=HTMLResponse)
        async def get_home():
            # Serve your HTML interface
            return HTMLResponse("""
                <!DOCTYPE html>
                <html>
                <head><title>Web HIL</title></head>
                <body>
                    <div id="messages"></div>
                    <input id="input" type="text" />
                    <button onclick="sendMessage()">Send</button>
                    <script>
                        const evtSource = new EventSource("/events");
                        evtSource.onmessage = (event) => {
                            const data = JSON.parse(event.data);
                            if (data.type === "agent_response") {
                                document.getElementById("messages").innerHTML += 
                                    `<p><strong>Agent:</strong> ${data.content}</p>`;
                            }
                        };
                        
                        async function sendMessage() {
                            const input = document.getElementById("input");
                            await fetch("/send", {
                                method: "POST",
                                headers: {"Content-Type": "application/json"},
                                body: JSON.stringify({message: input.value})
                            });
                            input.value = "";
                        }
                    </script>
                </body>
                </html>
            """)
        
        @app.post("/send")
        async def send_message(user_message: UserMessage):
            """Receive user input"""
            message = HILMessage(
                content=user_message.message,
                metadata={"timestamp": user_message.timestamp or datetime.now().isoformat()}
            )
            await self.user_input_queue.put(message)
            return {"status": "success"}
        
        @app.get("/events")
        async def stream_events():
            """SSE endpoint for real-time updates"""
            async def event_generator():
                while self.is_connected:
                    try:
                        message = await asyncio.wait_for(
                            self.sse_queue.get(), timeout=2.0
                        )
                        yield f"data: {json.dumps(message)}\n\n"
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream"
            )
        
        return app
    
    async def connect(self) -> None:
        """Start the web server."""
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        self.server = uvicorn.Server(config)
        
        # Start server in background
        loop = asyncio.get_running_loop()
        self.server_task = loop.create_task(self.server.serve())
        
        self.is_connected = True
        print(f"Web HIL started at http://{self.host}:{self.port}")
    
    async def disconnect(self) -> None:
        """Stop the web server."""
        self.is_connected = False
        self.shutdown_event.set()
        
        if self.server:
            self.server.should_exit = True
        
        if self.server_task:
            self.server_task.cancel()
    
    async def send_message(
        self, content: HILMessage, timeout: float | None = None
    ) -> bool:
        """Send message to browser via SSE."""
        if not self.is_connected:
            return False
        
        try:
            message = {
                "type": "agent_response",
                "content": content.content,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            
            await asyncio.wait_for(
                self.sse_queue.put(message),
                timeout=timeout
            )
            return True
            
        except (asyncio.QueueFull, asyncio.TimeoutError):
            return False
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    async def receive_message(
        self, timeout: float | None = None
    ) -> HILMessage | None:
        """Receive message from browser."""
        if not self.is_connected:
            return None
        
        input_task = asyncio.create_task(self.user_input_queue.get())
        shutdown_task = asyncio.create_task(self.shutdown_event.wait())
        
        try:
            done, pending = await asyncio.wait(
                [input_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=timeout
            )
            
            for task in pending:
                task.cancel()
            
            if input_task in done:
                return input_task.result()
            
            return None
            
        except asyncio.TimeoutError:
            input_task.cancel()
            shutdown_task.cancel()
            return None

# Usage
async def main():
    hil = WebHIL(port=8000)
    await hil.connect()
    
    # Keep running and processing messages
    while True:
        user_msg = await hil.receive_message(timeout=60.0)
        if user_msg:
            response = f"You said: {user_msg.content}"
            await hil.send_message(HILMessage(content=response))

asyncio.run(main())
```

## Best Practices

### 1. Connection State Management

Always track your connection state explicitly:

```python
def __init__(self):
    self.is_connected = False  # Clear state tracking

async def connect(self):
    # ... initialize resources ...
    self.is_connected = True  # Set after successful initialization

async def disconnect(self):
    self.is_connected = False  # Set immediately
    # ... cleanup ...
```

### 2. Timeout Handling

Always respect the timeout parameter:

```python
# Use asyncio.wait_for for operations with timeouts
await asyncio.wait_for(some_operation(), timeout=timeout)

# Use asyncio.wait for multiple events with timeout
done, pending = await asyncio.wait(
    tasks,
    return_when=asyncio.FIRST_COMPLETED,
    timeout=timeout
)
```

### 3. Error Handling

Don't raise exceptions from abstract methods - return failure indicators:

```python
async def send_message(self, content: HILMessage, timeout: float | None = None) -> bool:
    try:
        # ... send logic ...
        return True
    except Exception as e:
        logger.error(f"Failed to send: {e}")
        return False  # Don't raise, return False
```

### 4. Resource Cleanup

Always clean up resources in `disconnect()`:

```python
async def disconnect(self) -> None:
    self.is_connected = False
    
    # Cancel tasks
    if hasattr(self, 'task') and self.task:
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
    
    # Close connections
    if hasattr(self, 'connection') and self.connection:
        await self.connection.close()
```

### 5. Use asyncio Primitives

Leverage asyncio's built-in tools for message passing:

```python
# Queues for message passing
self.input_queue = asyncio.Queue(maxsize=100)
self.output_queue = asyncio.Queue(maxsize=100)

# Events for signaling
self.shutdown_event = asyncio.Event()
self.ready_event = asyncio.Event()

# Locks for synchronization
self.send_lock = asyncio.Lock()
```

## Testing Your Implementation

Here's a simple test template:

```python
import asyncio
import pytest
from railtracks.human_in_the_loop import HILMessage

@pytest.mark.asyncio
async def test_connection():
    hil = MyCustomHIL()
    
    # Test connection
    await hil.connect()
    assert hil.is_connected
    
    # Test sending
    result = await hil.send_message(HILMessage(content="test"))
    assert result is True
    
    # Test disconnection
    await hil.disconnect()
    assert not hil.is_connected

@pytest.mark.asyncio
async def test_timeout():
    hil = MyCustomHIL()
    await hil.connect()
    
    # Should timeout if no input
    result = await hil.receive_message(timeout=1.0)
    assert result is None
    
    await hil.disconnect()
```

## Reference Implementation

For a complete, production-ready example, see the `ChatUI` class in:
```
packages/railtracks/src/railtracks/human_in_the_loop/local_chat_ui.py
```

The `ChatUI` implementation demonstrates:

- FastAPI server with SSE for real-time updates
- Proper queue management with size limits
- Clean shutdown handling
- Static file serving for the UI
- Tool invocation updates (additional feature)
- Port availability checking
- Browser auto-opening

## Common Pitfalls

### 1. Blocking Operations

❌ **Don't block the event loop:**
```python
async def receive_message(self, timeout=None):
    return input("Enter message: ")  # WRONG: Blocks event loop
```

✅ **Use executor for blocking I/O:**
```python
async def receive_message(self, timeout=None):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, input, "Enter message: ")
```

### 2. Not Handling Disconnection

❌ **Don't forget to check connection state:**
```python
async def send_message(self, content, timeout=None):
    await self.queue.put(content)  # May fail if disconnected
    return True
```

✅ **Always check first:**
```python
async def send_message(self, content, timeout=None):
    if not self.is_connected:
        return False
    await self.queue.put(content)
    return True
```

### 3. Not Canceling Tasks

❌ **Don't leave tasks running:**
```python
async def receive_message(self, timeout=None):
    task1 = asyncio.create_task(self.queue.get())
    task2 = asyncio.create_task(self.event.wait())
    done, pending = await asyncio.wait([task1, task2], ...)
    return done.pop().result()  # Pending tasks still running!
```

✅ **Always cancel pending tasks:**
```python
async def receive_message(self, timeout=None):
    task1 = asyncio.create_task(self.queue.get())
    task2 = asyncio.create_task(self.event.wait())
    done, pending = await asyncio.wait([task1, task2], ...)
    
    for task in pending:
        task.cancel()  # Clean up!
    
    return done.pop().result()
```

## Next Steps

- See [Local Chat UI](local_chat_ui.md) for documentation on using the built-in ChatUI
- Check the [Human-in-the-Loop Overview](overview.md) for integration patterns
- Explore the examples in `examples/` for more use cases
