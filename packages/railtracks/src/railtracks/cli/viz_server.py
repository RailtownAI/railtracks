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
from .viz_api._debug import is_debug

app = FastAPI(
    title="railtracks visualizer API",
    description=(
        "HTTP surface behind the railtracks visualizer.\n\n"
        "**v1 (stable)** — file-based JSON endpoints on the bare `/api/…` "
        "paths. Serves the released visualizer build.\n\n"
        "**v2 (beta)** — event-stream endpoints backed by DuckDB on "
        "`/api/v2/…`. Under active development; shapes may change."
    ),
    openapi_tags=[
        {
            "name": "sessions",
            "description": "Session listing, per-session detail, and graph.",
        },
        {
            "name": "llm-traces",
            "description": "One row per LLM round trip, across sessions.",
        },
        {
            "name": "events",
            "description": "Raw event log — one row per event in the stream.",
        },
        {
            "name": "middleware",
            "description": "Middleware roll-ups, outcomes, and filter options.",
        },
        {
            "name": "v1 (stable)",
            "description": "Frozen file-based endpoints the released UI depends on.",
        },
    ],
)
# The v2 event-stream API, under its own `/api/v2` prefix so it sits beside the
# frozen v1 endpoints below rather than shadowing them. Included here, before the
# catch-all at the bottom of this file, because FastAPI matches in registration
# order and `/{full_path:path}` matches every remaining path — a router included
# after it would never be reached.
app.include_router(viz_api_router)

#: Which UI subdir under the railtracks home the catch-all serves from. The
#: default is the stable ``ui/``; ``RailtracksServer(ui_subdir="beta-ui")``
#: swaps it before ``server.run()`` fires.
_UI_SUBDIR: str = "ui"


def get_railtracks_dir() -> Path:
    """Get the .railtracks directory path"""
    return resolve_railtracks_home()


def get_data_dir(subdir: str) -> Path:
    """Get a data subdirectory path (e.g. evaluations, sessions)"""
    return get_railtracks_dir() / "data" / subdir


@app.get("/api/evaluations", tags=["v1 (stable)"])
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


# The v1 API, file-based and frozen.
#
# These stay exactly where they are, on the bare `/api/...` paths, because the
# released visualizer build is what calls them and it cannot be changed — if
# `.railtracks/ui/index.html` is missing at boot, `viz` downloads that build, so
# this is the UI an ordinary `railtracks viz` serves. v2 is in beta and lives
# under `/api/v2` instead, which keeps the stable client working untouched and
# makes "which API am I talking to" answerable from the URL alone.
#
# The two shapes are genuinely different, not versions of one thing: v1 returns a
# `runs` array per session with no rolled-up `status`, and feeding it to the v2
# SPA crashes it on the first missing field. Serving both is what lets that
# difference be harmless.


@app.get("/api/sessions", tags=["v1 (stable)"])
async def get_sessions():
    """Get all session JSON files from .railtracks/data/sessions/ (v1)"""
    sessions_dir = get_data_dir("sessions")
    sessions = []

    if sessions_dir.exists():
        for file_path in sessions_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = json.load(f)
                    sessions.append(content)
            except (json.JSONDecodeError, OSError) as e:
                print_error(f"Error reading session file {file_path.name}: {e}")

    return JSONResponse(content=sessions)


@app.get("/api/sessions/{guid}", tags=["v1 (stable)"])
async def get_session(guid: str):
    """Get a specific session JSON file by GUID from .railtracks/data/sessions/ (v1)"""
    sessions_dir = get_data_dir("sessions")
    file_path = sessions_dir / f"{guid}.json"
    if not file_path.exists():
        matches = list(sessions_dir.glob(f"*_{guid}.json"))
        if matches:
            file_path = matches[0]

    if not file_path.exists():
        return JSONResponse(content={"error": "Session not found"}, status_code=404)

    try:
        with open(file_path, encoding="utf-8") as f:
            content = json.load(f)
        return JSONResponse(content=content)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in {file_path.name}: {e}")
        return JSONResponse(content={"error": f"Invalid JSON: {e}"}, status_code=400)
    except Exception as e:
        print_error(f"Error reading session file {file_path.name}: {e}")
        return JSONResponse(content={"error": "Internal Server Error"}, status_code=500)


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_ui_or_404(full_path: str):
    """Serve UI files with SPA routing fallback (catch-all route)"""
    if full_path.startswith("api/"):
        return JSONResponse(content={"error": "Not Found"}, status_code=404)

    ui_dir = get_railtracks_dir() / _UI_SUBDIR
    ui_file = ui_dir / full_path
    if ui_file.exists() and ui_file.is_file():
        return FileResponse(str(ui_file))
    index_file = ui_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(content={"error": "File not found"}, status_code=404)


class RailtracksServer:
    """Main server class"""

    def __init__(
        self,
        port: int = DEFAULT_PORT,
        ui_subdir: str = "ui",
        beta: bool = False,
    ):
        self.port = port
        self.ui_subdir = ui_subdir
        self.beta = beta
        self.running = False
        self.config = None

    def start(self):
        """Start the FastAPI server"""
        global _UI_SUBDIR
        _UI_SUBDIR = self.ui_subdir
        self.running = True

        print_success(f"🚀 railtracks server running at http://localhost:{self.port}")
        print_status(f"📁 Serving files from: {get_railtracks_dir() / self.ui_subdir}")
        print_status(
            f"📖 Interactive API docs: http://localhost:{self.port}/docs"
        )

        if is_debug():
            print_status("📋 API endpoints:")
            print_status("   GET  /api/evaluations - Get all evaluation JSON files")
            print_status("   v1 (stable, file-based):")
            print_status("   GET  /api/sessions - Get all session JSON files")
            print_status("   GET  /api/sessions/{guid} - Get a specific session by GUID")
            print_status("   v2 (beta, event-stream):")
            for route in viz_api_router.routes:
                path = getattr(route, "path", None)
                if path:
                    print_status(f"   GET  {path}")

        print_status("Press Ctrl+C to stop the server")

        if self.beta:
            print_warning(
                "⚠️  Beta mode — this UI and the /api/v2 endpoints are under active "
                "development. Shapes, filter params and response fields may change "
                "between releases without warning. Use `railtracks viz` (no --beta) "
                "for a stable client."
            )

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
