#!/usr/bin/env python3
"""
Simple HTTP ChatUI - Interface for chatbot interaction with web UI

This implementation uses Python's built-in HTTP server to completely avoid
uvicorn/FastAPI cancellation issues during session termination.
"""

import asyncio
import json
import webbrowser
import threading
import time
import queue
from datetime import datetime
from importlib.resources import files
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

from .human_in_the_loop import HIL, HILMessage


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Threaded HTTP server that can handle multiple requests simultaneously."""
    daemon_threads = True


class ChatUIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the ChatUI server."""
    
    def __init__(self, chat_ui_instance, *args, **kwargs):
        self.chat_ui = chat_ui_instance
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Suppress default HTTP server logging."""
        pass
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/':
            self._serve_chat_interface()
        elif path == '/chat.css':
            self._serve_static_file('chat.css', 'text/css')
        elif path == '/chat.js':
            self._serve_static_file('chat.js', 'application/javascript')
        elif path == '/events':
            self._serve_sse()
        else:
            self._send_404()
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        if path == '/send_message':
            self._handle_send_message(post_data)
        elif path == '/disconnect':
            self._handle_disconnect()
        elif path == '/update_tools':
            self._handle_update_tools(post_data)
        else:
            self._send_404()
    
    def _serve_chat_interface(self):
        """Serve the main chat interface."""
        try:
            content = self.chat_ui._get_static_file_content("chat.html")
            self._send_response(200, content, 'text/html')
        except Exception as e:
            self._send_error(500, f"Error loading chat interface: {e}")
    
    def _serve_static_file(self, filename, content_type):
        """Serve static files."""
        try:
            content = self.chat_ui._get_static_file_content(filename)
            self._send_response(200, content, content_type)
        except Exception as e:
            self._send_error(500, f"Error loading {filename}: {e}")
    
    def _serve_sse(self):
        """Serve Server-Sent Events stream."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', f"http://{self.chat_ui.host}:{self.chat_ui.port}")
        self.send_header('Access-Control-Allow-Headers', 'Cache-Control')
        self.end_headers()
        
        try:
            while self.chat_ui.session_active:
                try:
                    # Non-blocking check for messages with timeout
                    message = self.chat_ui.outgoing_queue.get(timeout=1.0)
                    data = f"data: {json.dumps(message)}\n\n"
                    self.wfile.write(data.encode('utf-8'))
                    self.wfile.flush()
                    
                    # If this is a session end message, break the loop
                    if message.get("type") == "session_ended":
                        break
                        
                except queue.Empty:
                    # Send heartbeat if session still active
                    if self.chat_ui.session_active:
                        heartbeat = {"type": "heartbeat", "timestamp": datetime.now().isoformat()}
                        data = f"data: {json.dumps(heartbeat)}\n\n"
                        self.wfile.write(data.encode('utf-8'))
                        self.wfile.flush()
                
            # Send final message when session ends
            final_message = {"type": "session_ended", "timestamp": datetime.now().isoformat()}
            data = f"data: {json.dumps(final_message)}\n\n"
            self.wfile.write(data.encode('utf-8'))
            self.wfile.flush()
            
        except (ConnectionResetError, BrokenPipeError):
            # Client disconnected - this is normal and expected
            pass
        except Exception:
            # Any other error - just close the connection silently
            # No error logging to avoid spam during shutdown
            pass
    
    def _handle_send_message(self, post_data):
        """Handle incoming message from UI."""
        try:
            data = json.loads(post_data.decode('utf-8'))
            message = data.get('message', '')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            if self.chat_ui.session_active:
                message_data = HILMessage(
                    content=message,
                    metadata={"timestamp": timestamp}
                )
                self.chat_ui.incoming_queue.put(message_data)
                self._send_json_response({"status": "success", "message": "Message received"})
            else:
                self._send_json_response({"status": "session_ended"})
        except Exception as e:
            self._send_json_response({"status": "error", "message": str(e)})
    
    def _handle_disconnect(self):
        """Handle disconnect request from UI."""
        print("ChatUI: End session command received")
        self.chat_ui.session_active = False
        # Signal end of session to unblock receive_message
        self.chat_ui.incoming_queue.put(None)
        # Send session end message to SSE clients
        try:
            disconnect_msg = {"type": "session_ended", "timestamp": datetime.now().isoformat()}
            self.chat_ui.outgoing_queue.put_nowait(disconnect_msg)
        except queue.Full:
            pass  # Ignore if queue is full during shutdown
        self._send_json_response({"status": "disconnected"})
    
    def _handle_update_tools(self, post_data):
        """Handle tool update from UI."""
        try:
            data = json.loads(post_data.decode('utf-8'))
            if self.chat_ui.session_active:
                message = {"type": "tool_invoked", "data": data}
                self.chat_ui.outgoing_queue.put(message)
                self._send_json_response({"status": "success", "message": "Tool updated"})
            else:
                self._send_json_response({"status": "session_ended"})
        except Exception as e:
            self._send_json_response({"status": "error", "message": str(e)})
    
    def _send_response(self, status_code, content, content_type):
        """Send HTTP response."""
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))
    
    def _send_json_response(self, data):
        """Send JSON response."""
        content = json.dumps(data)
        self._send_response(200, content, 'application/json')
    
    def _send_error(self, status_code, message):
        """Send error response."""
        self._send_response(status_code, message, 'text/plain')
    
    def _send_404(self):
        """Send 404 Not Found response."""
        self._send_error(404, "Not Found")


class SimpleHTTPChatUI(HIL):
    """
    Simple HTTP-based interface for chatbot interaction with the web UI.
    
    Uses Python's built-in HTTP server to completely avoid uvicorn/FastAPI
    cancellation issues. No async complexity, just simple threading and queues.
    """

    def __init__(
        self, port: int = 8000, host: str = "127.0.0.1", auto_open: bool = True
    ):
        """
        Initialize the ChatUI interface.

        Args:
            port (int): Port number for the HTTP server
            host (str): Host to bind to (default: 127.0.0.1 for localhost only)
            auto_open (bool): automatically open the browser
        """
        self.port = port
        self.host = host
        self.auto_open = auto_open
        
        # Simple thread-safe queues (no asyncio)
        self.outgoing_queue = queue.Queue(maxsize=100)  # For SSE to UI
        self.incoming_queue = queue.Queue(maxsize=100)  # From UI to Python
        
        # Simple state flags
        self.is_connected = False
        self.session_active = True
        
        # Server running in separate thread
        self.server_thread = None
        self.httpd = None

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

    def _run_server_thread(self):
        """Run the HTTP server in a separate thread."""
        try:
            # Create handler class with chat_ui instance
            handler = lambda *args, **kwargs: ChatUIHandler(self, *args, **kwargs)
            
            # Create threaded HTTP server to handle multiple requests simultaneously
            self.httpd = ThreadedHTTPServer((self.host, self.port), handler)
            
            # Serve requests until shutdown
            self.httpd.serve_forever()
                        
        except Exception:
            # Server stopped - this is normal during shutdown
            pass

    def connect(self, content: HILMessage | None = None) -> None:
        """
        Creates or initializes the user interface component.

        Args:
            content: The initial content or prompt to display to the user.

        Raises:
            ConnectionError: If the interface cannot be established.
        """
        try:
            self.is_connected = True
            self.session_active = True
            
            # Start server in separate thread
            self.server_thread = threading.Thread(
                target=self._run_server_thread, 
                daemon=True
            )
            self.server_thread.start()
            
            # Give server time to start
            time.sleep(0.5)
            
            # Open browser if requested
            if self.auto_open:
                browser_url = f"http://{self.host}:{self.port}"
                webbrowser.open(browser_url)
                
            # Send initial message if provided
            if content:
                self.outgoing_queue.put({
                    "type": "assistant_response",
                    "data": content.content,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                })
                
        except Exception as e:
            self.is_connected = False
            raise ConnectionError(f"Failed to start ChatUI server: {e}")

    def disconnect(self) -> None:
        """
        Disconnects the user interface component.
        
        Simple disconnection that marks session as inactive.
        No complex async cancellation - just stops accepting new requests.
        """
        try:
            self.session_active = False
            self.is_connected = False
            
            # Signal any waiting receive_message calls
            self.incoming_queue.put(None)
            
            # Shutdown the server properly
            if hasattr(self, 'httpd') and self.httpd is not None:
                self.httpd.shutdown()
                self.httpd.server_close()
            
            # Clear remaining messages to prevent memory leaks
            while not self.outgoing_queue.empty():
                try:
                    self.outgoing_queue.get_nowait()
                except queue.Empty:
                    break
            
            while not self.incoming_queue.empty():
                try:
                    self.incoming_queue.get_nowait()
                except queue.Empty:
                    break
            
        except Exception as e:
            raise ConnectionError(f"Failed to disconnect ChatUI server: {e}")

    async def send_message(self, content: HILMessage, timeout: float | None = 5.0) -> bool:
        """
        Sends a message to the user through the interface.

        Args:
            content: The message content to send.
            timeout: The maximum time in seconds to wait for the message to be sent.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        if not self.is_connected or not self.session_active:
            print(f"ChatUI: Cannot send message - session not active")
            return False
            
        # Prepare message for UI
        message = {
            "type": "assistant_response",
            "data": content.content,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        
        # Override timestamp if provided in metadata
        if content.metadata and "timestamp" in content.metadata:
            message["timestamp"] = content.metadata["timestamp"]
        
        try:
            self.outgoing_queue.put_nowait(message)
            print(f"ChatUI: Message sent successfully")
            print(f"ChatUI: Sent response: {content.content}")
            return True
        except queue.Full:
            print(f"ChatUI: Outgoing queue is full")
            return False
        except Exception as e:
            print(f"ChatUI: Error sending message: {e}")
            return False

    async def receive_message(self, timeout: float | None = None) -> HILMessage | None:
        """
        Waits for the user to provide input.

        Args:
            timeout: The maximum time in seconds to wait for input.

        Returns:
            The user input if received within the timeout period, None otherwise.
        """
        if not self.is_connected or not self.session_active:
            return None
            
        try:
            # Use asyncio.run_in_executor to make the blocking queue.get() async
            loop = asyncio.get_event_loop()
            
            def get_message():
                try:
                    if timeout is not None:
                        return self.incoming_queue.get(timeout=timeout)
                    else:
                        return self.incoming_queue.get()
                except queue.Empty:
                    return None
                except Exception:
                    return None
            
            # Run the blocking queue operation in a thread pool
            message = await loop.run_in_executor(None, get_message)
            
            # Handle timeout or error (None message)
            if message is None:
                return None
            
            # Check if this is an "end" command
            if message.content.lower().strip() in ["end", "end session", "quit", "exit"]:
                print("ChatUI: End session command received")
                self.session_active = False
                return message
            
            print(f"ChatUI: Received message: {message.content}")
            return message
            
        except Exception as e:
            print(f"Error in receive_message: {e}")
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
        if not self.session_active:
            return
            
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
        try:
            self.outgoing_queue.put_nowait(message)
        except queue.Full:
            pass  # Ignore if queue is full


# Alias for compatibility
ChatUI = SimpleHTTPChatUI
