# Chat UI

The Chat UI component provides a simple interface for chatbot interaction with a web-based UI, supporting message sending and user input. It is designed to facilitate real-time communication between a chatbot and users through a web interface.

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

The Chat UI component is primarily used to enable real-time interaction between a chatbot and users via a web interface. It supports two main functionalities:

### 1.1 Sending Messages to the UI

This use case involves sending messages from the chatbot to the user interface, allowing the chatbot to communicate responses or information to the user.

python
async def send_message(content: str) -> None:
    """
    Send an assistant message to the chat interface.

    Args:
        content: The message content to send
    """
    message = {
        "type": "assistant_response",
        "data": content,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    await self.sse_queue.put(message)


### 1.2 Waiting for User Input

This use case involves waiting for user input from the chat interface, allowing the chatbot to receive and process user messages.

python
async def wait_for_user_input(timeout: Optional[float] = None) -> Optional[str]:
    """
    Wait for user input from the chat interface.

    Args:
        timeout: Maximum time to wait for input (None = wait indefinitely)

    Returns:
        User input string, or None if timeout/window closed
    """
    try:
        if timeout:
            user_msg = await asyncio.wait_for(
                self.user_input_queue.get(), timeout=timeout
            )
        else:
            user_msg = await self.user_input_queue.get()

        return user_msg.get("message") if user_msg else None

    except asyncio.TimeoutError:
        return None


## 2. Public API



## 3. Architectural Design

### 3.1 Core Design

- **FastAPI Server:** The component uses FastAPI to create a server that handles HTTP requests for sending messages and receiving user input.
- **Asynchronous Communication:** Utilizes asynchronous queues (`asyncio.Queue`) for handling messages and user inputs, ensuring non-blocking operations.
- **Static File Serving:** Static files such as HTML, CSS, and JavaScript are served to render the chat interface in the browser.

### 3.2 Data Flow

- **Message Flow:** Messages from the chatbot are placed in an SSE (Server-Sent Events) queue and streamed to the client.
- **User Input Flow:** User inputs are received via HTTP POST requests and placed in a queue for the chatbot to process.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **FastAPI and Uvicorn:** Ensure these are installed as they are critical for running the server.
- **Static Files:** The component relies on static files (`chat.html`, `chat.css`, `chat.js`) located in the `railtracks.visuals.browser` package.

### 4.2 Performance & Limitations

- **Concurrency:** The component is designed to handle multiple simultaneous connections using asynchronous programming.
- **Timeouts:** Proper handling of timeouts is crucial to avoid blocking operations.

## 5. Related Files

### 5.1 Code Files

- [`chat_ui.py`](../packages/railtracks/src/railtracks/utils/visuals/browser/chat_ui.py): Main implementation of the Chat UI component.

### 5.2 Related Feature Files

- [`llm_integration.md`](../docs/features/llm_integration.md): Documentation on how the Chat UI integrates with LLMs (Language Model Models).

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
