import asyncio
import json
import socket
import threading
import webbrowser
from datetime import datetime
from importlib.resources import files
from typing import Optional

import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from railtracks.llm import ToolCall, ToolResponse

from ..utils.logging.create import get_rt_logger
from .human_in_the_loop import HIL, HILMessage

logger = get_rt_logger("ChatUI")


class UserMessageAttachment(BaseModel):
    type: str  # "file" or "url"
    url: Optional[str] = None  # for URL type
    data: Optional[str] = None  # for file type (base64)
    name: Optional[str] = None  # optional name of the attachment

    def __init__(
        self,
        type: str,
        url: Optional[str] = None,
        data: Optional[str] = None,
        name: Optional[str] = None,
    ):
        if url is None and data is None:
            raise ValueError("Either 'url' or 'data' must be provided.")
        super().__init__(type=type, url=url, data=data, name=name)


class UIUserMessage(HILMessage):
    content: str
    attachments: Optional[list[UserMessageAttachment]] = None
    timestamp: Optional[str] = None
    metadata: Optional[dict] = None


class ToolInvocation(BaseModel):
    name: str
    identifier: str
    arguments: dict
    result: str
    success: bool = True


class ChatUI(HIL):
    """
    Simple interface for chatbot interaction with the web UI.

    Clean implementation that properly follows the HIL contract.
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

        # Simple message queues with reasonable size limits
        self.sse_queue = asyncio.Queue(maxsize=100)  # For SSE to UI
        self.user_input_queue = asyncio.Queue(maxsize=100)  # From UI to Python

        self.shutdown_event = asyncio.Event()  # For clean shutdown

        # Server state
        self.app = self._create_app()
        self.server_thread = None
        self.server_task = None
        self.server_started = threading.Event()
        self.is_connected = False

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
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Static file '{filename}' not found in package 'railtracks.utils.visuals.browser'. "
                f"Ensure the file exists in the package resources."
            ) from e
        except Exception as e:
            raise Exception(
                f"Failed to load static file '{filename}' for Chat UI: {type(e).__name__}: {str(e)}"
            ) from e

    def _define_endpoints(self, app: FastAPI):
        """Define the FastAPI endpoints."""

        @app.post("/send_message")
        async def send_message(user_message: UIUserMessage):
            """Receive user input from chat interface"""
            await self.user_input_queue.put(user_message)

            return {"status": "success", "message": "Message received"}

        @app.post("/update_tools")
        async def update_tools(tool_invocation: ToolInvocation):
            """Update the tools tab with a new tool invocation"""
            message = {"type": "tool_invoked", "data": tool_invocation.model_dump()}
            await self.sse_queue.put(message)
            return {"status": "success", "message": "Tool updated"}

        @app.post("/shutdown")
        async def shutdown():
            """Shutdown the chat interface"""
            self.is_connected = False
            await self.disconnect()
            return {"status": "success", "message": "Chat interface shutting down"}

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
                        heartbeat = {
                            "type": "heartbeat",
                            "timestamp": datetime.now().isoformat(),
                        }
                        yield f"data: {json.dumps(heartbeat)}\n\n"
                    except asyncio.CancelledError:
                        logger.debug("SSE event generator cancelled, this is expected.")
                        break

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

    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(title="ChatUI Server")
        self._define_endpoints(app)

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

    async def _run_server(self):
        if self.app is None:
            raise RuntimeError("App not initialized")

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="critical",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        try:
            await self.server.serve()
        except Exception as e:
            logger.error(f"Error occurred while running server: {e}")

    def _is_port_in_use(self, port: int, host: str) -> bool:
        """Checks if a port is already in use on the given host."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((host, port)) == 0

    async def connect(self) -> None:
        if self._is_port_in_use(self.port, self.host):
            error_msg = f"Port {self.port} is already in use. Cannot start ChatUI."
            logger.error(error_msg)
            raise ConnectionError(error_msg)

        localhost_url = f"http://{self.host}:{self.port}"

        self.server_task = asyncio.create_task(self._run_server())

        if self.auto_open:
            await asyncio.sleep(1)  # wait a bit before openning the browser
            webbrowser.open(localhost_url)

        self.is_connected = True
        logger.info(f"ChatUI server started at {localhost_url}")

    async def disconnect(self) -> None:
        """
        Disconnects the user interface component.
        """
        self.is_connected = False
        self.shutdown_event.set()

    async def send_message(
        self, content: HILMessage, timeout: float | None = 5.0
    ) -> bool:
        """
        Sends a message to the user through the interface.

        Args:
            content: The message content to send.
            timeout: The maximum time in seconds to wait for the message to be sent.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        if not self.is_connected:
            logger.warning("Cannot send message - not connected")
            return False

        # Prepare message for UI
        message = {
            "type": "assistant_response",
            "data": content.content,  # JavaScript expects data to be the content string directly
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }

        # Override timestamp if provided in metadata
        if content.metadata and "timestamp" in content.metadata:
            message["timestamp"] = content.metadata["timestamp"]

        try:
            # Use put_nowait for immediate, non-blocking operation
            await self.sse_queue.put(message)
            logger.debug(f"Message sent successfully: {message}")
            return True
        except asyncio.QueueFull:
            logger.warning(
                "Outgoing queue is full - likely no browser connected to consume messages"
            )
            # Don't wait indefinitely - just return False if queue is full
            # This prevents hanging when no browser is connected to the SSE endpoint
            return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def receive_message(
        self, timeout: float | None = None
    ) -> UIUserMessage | None:
        """
        Waits for the user to provide input.

        This method should block until input is received or the timeout is reached.

        Args:
            timeout: The maximum time in seconds to wait for input.

        Returns:
            The user input if received within the timeout period, None otherwise.
        """
        if not self.is_connected:
            return None

        tasks = [
            asyncio.create_task(self.user_input_queue.get()),
            asyncio.create_task(self.shutdown_event.wait()),
        ]

        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED, timeout=timeout
            )

            for task in pending:
                task.cancel()

            for task in done:
                if task is tasks[0]:  # user_input_queue.get()
                    message = task.result()
                    return message
                elif task is tasks[1]:  # shutdown_event.wait()
                    return None

            return None  # Timeout occurred

        except asyncio.TimeoutError:
            return None
        except asyncio.CancelledError:
            return None

    async def update_tools(
        self, tool_invocations: list[tuple[ToolCall, ToolResponse]]
    ) -> bool:
        """
        Send a tool invocation update to the chat interface.

        Args:
            tool_name: Name of the tool that was invoked
            tool_id: Unique identifier for the tool call
            arguments: Arguments passed to the tool
            result: Result returned by the tool
            success: Whether the tool call was successful
        """
        try:
            for tc, tr in tool_invocations:
                success = not str(tr.result).startswith(
                    "There was an error running the tool"
                )

                message = {
                    "type": "tool_invoked",
                    "data": {
                        "name": tc.name,
                        "identifier": tc.identifier,
                        "arguments": tc.arguments,
                        "result": str(tr.result),
                        "success": success,
                    },
                }
                await self.sse_queue.put(message)
                logger.debug(f"Tool Message sent successfully:\n {message}")

            return True
        except asyncio.QueueFull:
            logger.warning(
                "Outgoing queue is full - likely no browser connected to consume or there are too many tool updates"
            )
            return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
