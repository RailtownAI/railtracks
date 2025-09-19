from .human_in_the_loop import HIL, HILMessage

#!/usr/bin/env python3
"""
ChatUI - Simple interface for chatbot interaction with the web UI

Clean implementation that properly follows the HIL contract.
"""

import asyncio
import json
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
        
        # Simple message queues
        self.outgoing_messages = asyncio.Queue()  # For SSE to UI
        self.incoming_messages = asyncio.Queue()  # From UI to Python
        
        # Server state
        self.app = None
        self.server_task = None
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
            message_data = HILMessage(
                content=user_message.message,
                metadata={"timestamp": user_message.timestamp or datetime.now().isoformat()}
            )
            await self.incoming_messages.put(message_data)
            return {"status": "success", "message": "Message received"}

        @app.post("/update_tools")
        async def update_tools(tool_invocation: ToolInvocation):
            """Update the tools tab with a new tool invocation"""
            message = {"type": "tool_invoked", "data": tool_invocation.dict()}
            await self.outgoing_messages.put(message)
            return {"status": "success", "message": "Tool updated"}

        @app.get("/events")
        async def stream_events():
            """SSE endpoint for real-time updates"""

            async def event_generator():
                while self.is_connected:
                    try:
                        message = await asyncio.wait_for(
                            self.outgoing_messages.get(), timeout=1.0
                        )
                        yield f"data: {json.dumps(message)}\n\n"
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        heartbeat = {"type": "heartbeat", "timestamp": datetime.now().isoformat()}
                        yield f"data: {json.dumps(heartbeat)}\n\n"

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

    def connect(self, content: HILMessage | None = None) -> None:
        """
        Creates or initializes the user interface component.

        Args:
            content: The initial content or prompt to display to the user.

        Raises:
            ConnectionError: If the interface cannot be established.
        """
        try:
            # Create the FastAPI app
            self.app = self._create_app()
            self.is_connected = True
            
            # Start the server in a background task
            async def run_server():
                if self.app is None:
                    raise RuntimeError("App not initialized")
                    
                config = uvicorn.Config(
                    app=self.app,
                    host=self.host,
                    port=self.port,
                    log_level="error",
                    access_log=False
                )
                server = uvicorn.Server(config)
                await server.serve()
            
            # Get or create event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # We're not in an async context, create a new loop
                import threading
                import time
                
                def start_server():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(run_server())
                
                server_thread = threading.Thread(target=start_server, daemon=True)
                server_thread.start()
                
                # Give server a moment to start
                time.sleep(1)
                
                # Open browser if requested
                if self.auto_open:
                    webbrowser.open(f"http://{self.host}:{self.port}")
                return
            
            # We're in an async context, create task
            self.server_task = loop.create_task(run_server())
            
            # Send initial message if provided
            if content:
                loop.create_task(self.send_message(content))
            
            # Open browser if requested
            if self.auto_open:
                webbrowser.open(f"http://{self.host}:{self.port}")
                
        except Exception as e:
            self.is_connected = False
            raise ConnectionError(f"Failed to start ChatUI server: {e}")

    def disconnect(self) -> None:
        """
        Disconnects the user interface component.

        Raises:
            ConnectionError: If the interface cannot be properly closed.
        """
        try:
            self.is_connected = False
            
            # Cancel server task if it exists
            if self.server_task and not self.server_task.done():
                self.server_task.cancel()
            
            # Clear queues
            while not self.outgoing_messages.empty():
                try:
                    self.outgoing_messages.get_nowait()
                except asyncio.QueueEmpty:
                    break
                    
            while not self.incoming_messages.empty():
                try:
                    self.incoming_messages.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
            self.server_task = None
            self.app = None
            
        except Exception as e:
            raise ConnectionError(f"Failed to disconnect ChatUI server: {e}")

    async def send_message(self, content: HILMessage, timeout: float | None = None) -> bool:
        """
        Sends a message to the user through the interface.

        Args:
            content: The message content to send.
            timeout: The maximum time in seconds to wait for the message to be sent.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        if not self.is_connected:
            return False
            
        # Prepare message for UI
        message = {
            "type": "assistant_response",
            "data": {
                "content": content.content,
                "metadata": content.metadata
            },
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        
        # Override timestamp if provided in metadata
        if content.metadata and "timestamp" in content.metadata:
            message["timestamp"] = content.metadata["timestamp"]
        
        try:
            if timeout is not None:
                await asyncio.wait_for(
                    self.outgoing_messages.put(message),
                    timeout=timeout
                )
            else:
                await self.outgoing_messages.put(message)
            return True
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False

    async def receive_message(self, timeout: float | None = None) -> HILMessage | None:
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
            
        try:
            if timeout is not None:
                message = await asyncio.wait_for(
                    self.incoming_messages.get(),
                    timeout=timeout
                )
            else:
                message = await self.incoming_messages.get()
            
            return message
            
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

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
        await self.outgoing_messages.put(message)
