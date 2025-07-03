#!/usr/bin/env python3
"""
ChatUI - Simple interface for chatbot interaction with the web UI

This class provides a minimal API for chatbots to interact with the real-time
chat interface. Focused on the two core needs:
1. Sending messages to the UI
2. Waiting for user input
"""
import asyncio
import uvicorn
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json

import threading
import uvicorn
class UserMessage(BaseModel):
    message: str
    timestamp: Optional[str] = None


class ChatUI:
    """
    Simple interface for chatbot interaction with the web UI.
    
    Provides just the essential methods needed for tool-calling LLM integration:
    - Send messages to the chat interface
    - Wait for user input with timeout support
    - Set up and manage the FastAPI server
    """
    
    def __init__(self, port: int = 8000):
        """
        Initialize the ChatUI interface.
        
        Args:
            port: Port number for the FastAPI server
        """
        self.port = port
        self.sse_queue = asyncio.Queue()
        self.user_input_queue = asyncio.Queue()
        self.app = self._create_app()
        self.server_task = None
    
    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            yield
            # Shutdown (nothing to do)
        
        app = FastAPI(title="ChatUI Server", lifespan=lifespan)
        
        # Enable CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @app.post("/send_message")
        async def send_message(user_message: UserMessage):
            """Receive user input from chat interface"""
            message_data = {
                "message": user_message.message,
                "timestamp": user_message.timestamp or datetime.now().isoformat()
            }
            await self.user_input_queue.put(message_data)
            return {"status": "success", "message": "Message received"}
        
        @app.get("/events")
        async def stream_events():
            """SSE endpoint for real-time updates"""
            async def event_generator():
                while True:
                    try:
                        message = await asyncio.wait_for(self.sse_queue.get(), timeout=1.0)
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
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control",
                }
            )
        
        @app.get("/", response_class=HTMLResponse)
        async def get_chat_interface():
            """Serve the chat interface HTML"""
            with open("src/requestcompletion/visuals/browser/chat.html", "r") as f:
                return HTMLResponse(f.read())
        
        return app
    
    async def send_message(self, content: str) -> None:
        """
        Send an assistant message to the chat interface.
        
        Args:
            content: The message content to send
        """
        message = {
            "type": "assistant_response",
            "data": content,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        await self.sse_queue.put(message)
    
    async def wait_for_user_input(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Wait for user input from the chat interface.
        
        Args:
            timeout: Maximum time to wait for input (None = wait indefinitely)
            
        Returns:
            User input string, or None if timeout/window closed
        """
        try:
            if timeout:
                user_msg = await asyncio.wait_for(self.user_input_queue.get(), timeout=timeout)
            else:
                user_msg = await self.user_input_queue.get()
                
            return user_msg.get("message") if user_msg else None
            
        except asyncio.TimeoutError:
            return None
    
    def start_server(self):
        """Start the FastAPI server"""
        print("🤖 Starting ChatUI Server...")
        print("📡 SSE endpoint: http://localhost:8000/events")
        print("💬 Message endpoint: http://localhost:8000/send_message")
        print("🌐 Open browser: http://localhost:8000")
        
        uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="info")
    
    def start_server_async(self):
        """Start the FastAPI server in the background"""
        localhost_url = f"http://localhost:{self.port}"
        
        if self.server_task is None:
            print("🤖 Starting ChatUI Server...")
            print(f"📡 SSE endpoint: {localhost_url}/events")
            print(f"💬 Message endpoint: {localhost_url}/send_message")
            print(f"🌐 Open browser: {localhost_url}")
            
            def run_server():
                uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="warning")
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            # # Give server time to start
            # await asyncio.sleep(1)
        
        return localhost_url
