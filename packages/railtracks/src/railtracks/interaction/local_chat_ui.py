from .human_in_the_loop import HIL, HILMessage

#!/usr/bin/env python3
"""
ChatUI - Simple interface for chatbot interaction with the web UI

This class provides a minimal API for chatbots to interact with the real-time
chat interface. Focused on the two core needs:
1. Sending messages to the UI
2. Waiting for user input
"""

import asyncio
import json
import threading
import webbrowser
from datetime import datetime
from importlib.resources import files
from typing import Optional

import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel


class UIUserMessage(BaseModel):
    message: str
    timestamp: Optional[str] = None


class ToolInvocation(BaseModel):
    name: str
    identifier: str
    arguments: dict
    result: str
    success: bool = True


class ChatUI(HIL):
    """
    Simple interface for chatbot interaction with the web UI.

    Provides just the essential methods needed for tool-calling LLM integration:
    - Send messages to the chat interface
    - Wait for user input with timeout support
    - Set up and manage the FastAPI server
    """

    def __init__(
        self, port: int = 8000, host: str = "127.0.0.1", auto_open: bool = True
    ):
        """
        Initialize the ChatUI interface.

        Args:
            port (int): Port number for the FastAPI server
            host (str): Host to bind to (default: 127.0.0.1 for localhost only)
            auto_open (bool): automatically open the browser
        """
        self.port = port
        self.host = host
        self.auto_open = auto_open
        self.sse_queue = asyncio.Queue()
        self.user_input_queue = asyncio.Queue()
        self.app = self._create_app()
        self.server_thread = None
        self._server = None
        self._shutdown_event = threading.Event()

    def _get_static_file_content(self, filename: str) -> str:
        """
        Get the content of a static file from the package.

        Args:
            filename: Name of the file (e.g., 'chat.html', 'chat.css', 'chat.js')

        Returns:
            Content of the file as a string

        Raises:
            FileNotFoundError: If the static file cannot be found
        """
        try:
            package_files = files("railtracks.utils.visuals.browser")
            return (package_files / filename).read_text(encoding="utf-8")
        except Exception as e:
            raise Exception(
                f"Exception occurred loading static '{filename}' for Chat UI"
            ) from e

    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(title="ChatUI Server")

        @app.post("/send_message")
        async def send_message(user_message: UIUserMessage):
            """Receive user input from chat interface"""
            message_data = {
                "message": user_message.message,
                "timestamp": user_message.timestamp or datetime.now().isoformat(),
            }
            await self.user_input_queue.put(message_data)
            return {"status": "success", "message": "Message received"}

        @app.post("/update_tools")
        async def update_tools(tool_invocation: ToolInvocation):
            """Update the tools tab with a new tool invocation"""
            message = {"type": "tool_invoked", "data": tool_invocation.dict()}
            await self.sse_queue.put(message)
            return {"status": "success", "message": "Tool updated"}

        @app.get("/events")
        async def stream_events():
            """SSE endpoint for real-time updates"""

            async def event_generator():
                while True:
                    try:
                        message = await asyncio.wait_for(
                            self.sse_queue.get(), timeout=1.0
                        )
                        yield f"data: {json.dumps(message)}\n\n"
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": f"http://{self.host}:{self.port}",
                    "Access-Control-Allow-Headers": "Cache-Control",
                },
            )

        @app.get("/", response_class=HTMLResponse)
        async def get_chat_interface():
            """Serve the chat interface HTML"""
            content = self._get_static_file_content("chat.html")
            return HTMLResponse(content)

        @app.get("/chat.css")
        async def get_chat_css():
            """Serve the chat CSS file"""
            content = self._get_static_file_content("chat.css")
            return Response(content, media_type="text/css")

        @app.get("/chat.js")
        async def get_chat_js():
            """Serve the chat JavaScript file"""
            content = self._get_static_file_content("chat.js")
            return Response(content, media_type="application/javascript")

        return app

    async def send_message(self, content: HILMessage, timeout: float | None = None) -> bool:
        """
        Send an assistant message to the chat interface.

        Args:
            content: The message content to send.
            timeout: Maximum time to wait for the message to be sent.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        # Extract timestamp from metadata if provided, otherwise use current time
        timestamp = datetime.now().strftime("%H:%M:%S")
        if content.metadata and "timestamp" in content.metadata:
            timestamp = content.metadata["timestamp"]
        
        message = {
            "type": "assistant_response",
            "data": {
                "content": content.content,
                "metadata": content.metadata
            },
            "timestamp": timestamp,
        }
        
        try:
            if timeout:
                await asyncio.wait_for(
                    self.sse_queue.put(message),
                    timeout=timeout,
                )
            else:
                await self.sse_queue.put(message)
            return True
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False

    async def update_tools(
        self,
        tool_name: str,
        tool_id: str,
        arguments: dict,
        result: str,
        success: bool = True,
    ) -> None:
        """
        Send a tool invocation update to the chat interface.

        Args:
            tool_name: Name of the tool that was invoked
            tool_id: Unique identifier for the tool call
            arguments: Arguments passed to the tool
            result: Result returned by the tool
            success: Whether the tool call was successful
        """
        message = {
            "type": "tool_invoked",
            "data": {
                "name": tool_name,
                "identifier": tool_id,
                "arguments": arguments,
                "result": result,
                "success": success,
            },
        }
        await self.sse_queue.put(message)

    async def receive_message(self, timeout: float | None = None) -> HILMessage | None:
        """
        Wait for user input from the chat interface.

        Args:
            timeout: Maximum time to wait for input (None = wait indefinitely)

        Returns:
            User input message, or None if timeout/window closed
        """
        try:
            if timeout:
                user_msg = await asyncio.wait_for(
                    self.user_input_queue.get(), timeout=timeout
                )
            else:
                user_msg = await self.user_input_queue.get()

            return HILMessage(content=user_msg.get("message")) if user_msg else None

        except asyncio.TimeoutError:
            return None

    def run_server(self):
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")

    def connect(self, content: HILMessage | None = None) -> None:
        """Start the FastAPI server in the background"""
        try:
            localhost_url = f"http://{self.host}:{self.port}"

            if self.server_thread is None:
                self.server_thread = threading.Thread(
                    target=self.run_server, daemon=True
                )
                self.server_thread.start()

            if self.auto_open:
                webbrowser.open(localhost_url)
        except Exception:
            raise ConnectionError("Failed to start ChatUI server")
        
    def disconnect(self) -> None:
        """Disconnect the ChatUI interface (not implemented)"""
        # Note: Proper server shutdown is complex; for now, we leave it running in daemon thread
        pass