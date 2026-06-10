"""FastAPI + uvicorn visualizer server (requires railtracks[visual]).

Two API surfaces coexist during the storage migration:
- legacy ``/api/sessions*`` endpoints reading whole JSON files (removed
  once the visualizer has switched over)
- ``/api/v2/*`` endpoints backed by the SQLite workspace DB, which
  return typed slices (runs, nodes, edges, llm-calls, tool-calls)
  instead of the full nested tree
"""

import json
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, select

from railtracks.paths import resolve_railtracks_home
from railtracks.persistence.connection import get_engine
from railtracks.persistence.export import legacy_session_payload
from railtracks.persistence.models import (
    LLMCallRow,
    MessageRow,
    NodeRow,
    RequestRow,
    RunRow,
    SessionRow,
    ToolCallRow,
)

from .constants import DEFAULT_PORT
from .io import print_error, print_status, print_success, print_warning

app = FastAPI()

_engine = None


def get_db_engine():
    global _engine
    if _engine is None:
        _engine = get_engine()
        # a fresh workspace has no DB until the first session runs; make
        # sure the schema exists so endpoints return empty lists, not 500s
        SQLModel.metadata.create_all(_engine)
    return _engine


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


@app.get("/api/sessions")
async def get_sessions():
    """All sessions in the legacy full-payload shape, rebuilt from SQLite.

    The response shape matches what this endpoint returned when it read
    JSON files, so the embedded UI keeps working unchanged.
    """
    with DBSession(get_db_engine()) as s:
        session_ids = s.exec(
            select(SessionRow.session_id).order_by(SessionRow.start_time.desc())
        ).all()

    engine = get_db_engine()
    payloads = []
    for session_id in session_ids:
        payload = legacy_session_payload(engine, session_id)
        if payload is not None:
            payloads.append(payload)
    return JSONResponse(content=payloads)


@app.get("/api/sessions/{guid}")
async def get_session(guid: str):
    """One session in the legacy full-payload shape, rebuilt from SQLite."""
    payload = legacy_session_payload(get_db_engine(), guid)
    if payload is None:
        return JSONResponse(content={"error": "Session not found"}, status_code=404)
    return JSONResponse(content=payload)


# --------------------------------------------------------------------------
# v2 endpoints — SQLite-backed typed queries
# --------------------------------------------------------------------------


@app.get("/api/v2/sessions")
async def v2_list_sessions():
    """Lightweight session list with per-session token/cost aggregates.

    The aggregates are computed in SQL so list sorting in the UI no
    longer needs to walk every node of every run.
    """
    with DBSession(get_db_engine()) as s:
        sessions = s.exec(
            select(SessionRow).order_by(SessionRow.start_time.desc())
        ).all()
        aggregates = {
            row[0]: row
            for row in s.exec(
                select(
                    LLMCallRow.session_id,
                    func.sum(LLMCallRow.input_tokens),
                    func.sum(LLMCallRow.output_tokens),
                    func.sum(LLMCallRow.total_cost),
                    func.count(LLMCallRow.call_id),
                ).group_by(LLMCallRow.session_id)
            ).all()
        }
        run_counts = {
            row[0]: row[1]
            for row in s.exec(
                select(RunRow.session_id, func.count(RunRow.run_id)).group_by(
                    RunRow.session_id
                )
            ).all()
        }

    payload = []
    for sess in sessions:
        agg = aggregates.get(sess.session_id)
        payload.append(
            {
                **sess.model_dump(),
                "run_count": run_counts.get(sess.session_id, 0),
                "total_input_tokens": agg[1] if agg else 0,
                "total_output_tokens": agg[2] if agg else 0,
                "total_cost": agg[3] if agg else 0.0,
                "llm_call_count": agg[4] if agg else 0,
            }
        )
    return JSONResponse(content=payload)


@app.get("/api/v2/sessions/{session_id}/runs")
async def v2_session_runs(session_id: str):
    with DBSession(get_db_engine()) as s:
        runs = s.exec(
            select(RunRow)
            .where(RunRow.session_id == session_id)
            .order_by(RunRow.start_time)
        ).all()
    return JSONResponse(content=[r.model_dump() for r in runs])


@app.get("/api/v2/runs/{run_id}/nodes")
async def v2_run_nodes(run_id: str):
    with DBSession(get_db_engine()) as s:
        nodes = s.exec(select(NodeRow).where(NodeRow.run_id == run_id)).all()
    return JSONResponse(content=[n.model_dump() for n in nodes])


@app.get("/api/v2/runs/{run_id}/edges")
async def v2_run_edges(run_id: str):
    """Requests of a run with node names pre-joined — the frontend no
    longer needs the nodes.find() lookup per edge."""
    with DBSession(get_db_engine()) as s:
        rows = s.exec(
            select(RequestRow, NodeRow.name, NodeRow.node_type)
            .join(NodeRow, RequestRow.sink_node_uuid == NodeRow.node_uuid)
            .where(RequestRow.run_id == run_id)
            .order_by(RequestRow.created_stamp_step)
        ).all()
    return JSONResponse(
        content=[
            {
                **request.model_dump(),
                "sink_node_name": sink_name,
                "sink_node_type": sink_type,
            }
            for request, sink_name, sink_type in rows
        ]
    )


@app.get("/api/v2/llm-calls")
async def v2_llm_calls(
    session_id: str | None = None,
    model: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    """Flat, paginated LLM-call list across sessions (visualizer #239)."""
    with DBSession(get_db_engine()) as s:
        stmt = (
            select(LLMCallRow, NodeRow.name, SessionRow.flow_name)
            .join(NodeRow, LLMCallRow.node_uuid == NodeRow.node_uuid)
            .join(SessionRow, LLMCallRow.session_id == SessionRow.session_id)
        )
        if session_id is not None:
            stmt = stmt.where(LLMCallRow.session_id == session_id)
        if model is not None:
            stmt = stmt.where(LLMCallRow.model_name == model)
        stmt = stmt.order_by(LLMCallRow.call_id.desc()).offset(offset).limit(limit)
        rows = s.exec(stmt).all()
    return JSONResponse(
        content=[
            {
                **call.model_dump(),
                "node_name": node_name,
                "flow_name": flow_name,
            }
            for call, node_name, flow_name in rows
        ]
    )


@app.get("/api/v2/sessions/{session_id}/llm-calls")
async def v2_session_llm_calls(session_id: str):
    return await v2_llm_calls(session_id=session_id, limit=10_000)


@app.get("/api/v2/tool-calls")
async def v2_tool_calls(name: str | None = None, run_id: str | None = None):
    """Tool invocations filterable by name and run (visualizer #126)."""
    with DBSession(get_db_engine()) as s:
        stmt = select(ToolCallRow)
        if run_id is not None:
            stmt = (
                stmt.join(MessageRow, ToolCallRow.message_id == MessageRow.message_id)
                .join(LLMCallRow, MessageRow.call_id == LLMCallRow.call_id)
                .join(NodeRow, LLMCallRow.node_uuid == NodeRow.node_uuid)
                .where(NodeRow.run_id == run_id)
            )
        if name is not None:
            stmt = stmt.where(ToolCallRow.name == name)
        rows = s.exec(stmt).all()
    return JSONResponse(content=[r.model_dump() for r in rows])


@app.get("/api/v2/sessions/{session_id}/full")
async def v2_session_full(session_id: str):
    """The legacy nested-tree shape, rebuilt from SQL.

    Bridge endpoint: lets the visualizer keep its current parsing code
    while it migrates page-by-page to the typed endpoints above.
    """
    payload = legacy_session_payload(get_db_engine(), session_id)
    if payload is None:
        return JSONResponse(content={"error": "Session not found"}, status_code=404)
    return JSONResponse(content=payload)


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
        print_status("   GET  /api/sessions - All sessions (legacy shape, SQLite-backed)")
        print_status("   GET  /api/sessions/{guid} - One session by GUID")
        print_status("   GET  /api/v2/* - Typed SQL endpoints (sessions, runs, llm-calls, tool-calls)")
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
