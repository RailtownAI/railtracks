"""FastAPI + uvicorn visualizer server (requires railtracks[visual])."""

import json
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from railtracks.paths import resolve_railtracks_home

from .constants import DEFAULT_PORT
from .io import print_error, print_status, print_success, print_warning
from .viz_api import router as viz_api_router

app = FastAPI()
# Session endpoints backed by the event-stream query layer. Must be included
# before the catch-all below, which matches every remaining path.
app.include_router(viz_api_router)


def get_railtracks_dir() -> Path:
    """Get the .railtracks directory path"""
    return resolve_railtracks_home()


def get_data_dir(subdir: str) -> Path:
    """Get a data subdirectory path (e.g. evaluations, sessions)"""
    return get_railtracks_dir() / "data" / subdir


@app.get("/api/evaluations")
async def get_evaluations():
    """Get all evaluation JSON files from .railtracks/data/evaluations/"""
    evaluations_dir = get_data_dir("evaluations")
    evaluations = []

    if evaluations_dir.exists():
        for file_path in evaluations_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = json.load(f)
                    evaluations.append(content)
            except (json.JSONDecodeError, OSError) as e:
                print_error(f"Error reading evaluation file {file_path.name}: {e}")

    return JSONResponse(content=evaluations)


@app.get("/{full_path:path}")
async def serve_ui_or_404(full_path: str):
    """Serve UI files with SPA routing fallback (catch-all route)"""
    if full_path.startswith("api/"):
        return JSONResponse(content={"error": "Not Found"}, status_code=404)

    ui_dir = get_railtracks_dir() / "ui"
    ui_file = ui_dir / full_path
    if ui_file.exists() and ui_file.is_file():
        return FileResponse(str(ui_file))
    index_file = ui_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(content={"error": "File not found"}, status_code=404)


class RailtracksServer:
    """Main server class"""

    def __init__(self, port=DEFAULT_PORT):
        self.port = port
        self.running = False
        self.config = None

    def start(self):
        """Start the FastAPI server"""
        self.running = True

        print_success(f"🚀 railtracks server running at http://localhost:{self.port}")
        print_status(f"📁 Serving files from: {get_railtracks_dir() / 'ui'}")
        print_status("📋 API endpoints:")
        print_status("   GET  /api/evaluations - Get all evaluation JSON files")
        print_status("   GET  /api/sessions - List sessions from the event stream")
        print_status("   GET  /api/sessions/{session_id} - Session detail + tree")
        print_status("   GET  /api/sessions/{session_id}/nodes/{node_id} - Node detail")
        print_status("   GET  /api/sessions/{session_id}/graph - Session graph")
        print_status("   GET  /api/llm-traces - LLM calls across sessions")
        print_status("   GET  /api/llm-traces/stats - Roll-up over the same filters")
        print_status(
            "   GET  /api/llm-traces/filters - Values the LLM trace filters accept"
        )
        print_status("   GET  /api/events - Raw event stream, one row per event")
        print_status("   GET  /api/events/stats - Roll-up over the same filters")
        print_status("   GET  /api/events/filters - Values the event filters accept")
        print_status("Press Ctrl+C to stop the server")

        def open_browser():
            time.sleep(1)
            url = f"http://localhost:{self.port}"
            print_status(f"Opening browser to {url}")
            try:
                webbrowser.open(url)
            except Exception as e:
                print_warning(f"Could not open browser automatically: {e}")
                print_status(f"Please manually open: {url}")

        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()

        try:
            config = uvicorn.Config(
                app,
                host="localhost",
                port=self.port,
                log_level="info",
                access_log=False,
            )
            server = uvicorn.Server(config)
            self.config = config
            server.run()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the server and cleanup"""
        if self.running:
            print_status("Shutting down railtracks...")
            self.running = False

            print_success("railtracks stopped.")
