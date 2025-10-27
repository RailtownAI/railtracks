# Extending the HIL Abstract Class

The Human-in-the-Loop (HIL) interface allows you to create custom communication channels between your Railtracks agents and users. This guide shows you how to implement your own HIL interface by extending the `HIL` abstract class.

## Overview

The `HIL` abstract class defines a contract for bidirectional communication with users. Any implementation must provide four key methods:

- `connect()` - Initialize the communication channel
- `disconnect()` - Clean up resources
- `send_message()` - Send messages to the user
- `receive_message()` - Receive input from the user

??? info "The HIL Interface: [human_in_the_loop.py](packages/railtracks/src/railtracks/human_in_the_loop/human_in_the_loop.py)"

    ```python
    --8<-- "packages/railtracks/src/railtracks/human_in_the_loop/human_in_the_loop.py"
    ```

## Implementation Guide

### Basic Structure

Create a class that inherits from `HIL` and initialize the necessary state for your communication channel. At minimum, you'll need to track connection status and set up mechanisms for bidirectional communication (such as queues or event handlers).

Below are some of our suggestions for such implementation, however, your way of defining it is completely up to you and your system design choices.

??? info "Suggested Steps"
    ### 1. Implement connect()

    The `connect()` method initializes all resources needed for communication with users. This is where you:

    - Start any servers or services (web servers, WebSocket connections, messaging clients)
    - Initialize communication channels
    - Set up authentication or session management if needed
    - Update the connection state to indicate the channel is ready

    **Key considerations:**

    - Track connection state explicitly
    - Raise appropriate exceptions if initialization fails
    - Make the method safe to call multiple times if possible

    ### 2. Implement disconnect()

    The `disconnect()` method performs cleanup of all resources. This should:

    - Update connection state immediately
    - Close servers, connections, or file handles
    - Cancel any running background tasks
    - Clean up gracefully even if resources weren't fully initialized

    **Key considerations:**

    - Set connection state to `False` at the start
    - Don't raise exceptions during cleanup - log errors instead
    - Make it safe to call multiple times

    ### 3. Implement send_message()

    This method sends messages from your agent to the user through your communication channel. It should:

    - Verify the connection is active before attempting to send
    - Format the message appropriately for your channel
    - Transmit the message through your communication mechanism
    - Return `True` on success, `False` on any failure
    - Respect the timeout parameter if provided

    **Key considerations:**

    - Always check connection state first
    - Return `False` rather than raising exceptions on failure
    - Handle timeouts and queue full conditions gracefully
    - Log warnings or errors for debugging

    ### 4. Implement receive_message()

    This method waits for and receives input from the user. It should:

    - Verify the connection is active
    - Wait for user input through your communication channel
    - Handle shutdown events to allow clean termination
    - Return a `HILMessage` when input is received
    - Return `None` on timeout, disconnection, or shutdown

    **Key considerations:**

    - Return `None` for timeout, disconnection, or shutdown scenarios
    - Handle multiple concurrent events (input arrival and shutdown signals)
    - Always cancel pending tasks to prevent resource leaks
    - Respect timeout parameters and handle timeout exceptions

## Reference Implementation

For a complete example, see the `ChatUI` class in [local_chat_ui.py](packages/railtracks/src/railtracks/human_in_the_loop/local_chat_ui.py)


The `ChatUI` implementation demonstrates:

- FastAPI server with SSE for real-time updates
- Proper queue management with size limits
- Clean shutdown handling
- Static file serving for the UI
- Tool invocation updates (additional feature)
- Port availability checking
- Browser auto-opening

??? tip "Common Pitfalls"

    ### 1. Blocking Operations

    **Don't block the event loop:**
    ```python
    async def receive_message(self, timeout=None):
        return input("Enter message: ")  # WRONG: Blocks event loop
    ```

    **Use asyncio.to_thread for blocking I/O:**
    ```python
    async def receive_message(self, timeout=None):
        return await asyncio.to_thread(input, "Enter message: ")
    ```

    ### 2. Not Handling Disconnection

    **Don't forget to check connection state:**
    ```python
    async def send_message(self, content, timeout=None):
        await self.queue.put(content)  # May fail if disconnected
        return True
    ```

    **Always check first:**
    ```python
    async def send_message(self, content, timeout=None):
        if not self.is_connected:
            return False
        await self.queue.put(content)
        return True
    ```

    ### 3. Not Canceling Tasks

    **Don't leave tasks running:**
    ```python
    async def receive_message(self, timeout=None):
        task1 = asyncio.create_task(self.queue.get())
        task2 = asyncio.create_task(self.event.wait())
        done, pending = await asyncio.wait([task1, task2], ...)
        return done.pop().result()  # Pending tasks still running!
    ```

    **Always cancel pending tasks:**
    ```python
    async def receive_message(self, timeout=None):
        task1 = asyncio.create_task(self.queue.get())
        task2 = asyncio.create_task(self.event.wait())
        done, pending = await asyncio.wait([task1, task2], ...)
        
        for task in pending:
            task.cancel()  # Clean up!
        
        return done.pop().result()
    ```
## Last step: Updating the `interactive` method
Currently, the **`interactive`** method only supports `ChatUI` implementation, but you could easily modify it, append to it, or completely write new logic to work with your specific child class of `HIL`.

```python
--8<-- "packages/railtracks/src/railtracks/interaction/interactive.py:120:153"
```

## Share your work

We're excited to see what implemenations you come up with and welcome incorporating your suggested changes or new implementations to the framework!

## Next Steps

- See [Local Chat UI](local_chat_ui.md) for documentation on using the built-in ChatUI
- Check the [Human-in-the-Loop Overview](overview.md) for integration patterns