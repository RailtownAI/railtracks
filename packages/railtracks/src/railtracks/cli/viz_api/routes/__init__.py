"""FastAPI routes for the visualizer, backed by the event-stream query layer.

Sub-routers live in per-resource modules (``sessions``, ``llm_traces``,
``events``, ``middleware``); this package composes them under the shared
``/api/v2`` prefix. The v1 file-based endpoints in ``viz_server.py`` keep
their bare ``/api/`` paths because the released visualizer build calls them
and cannot be changed.
"""

from fastapi import APIRouter

from . import events, llm_traces, middleware, sessions

router = APIRouter(prefix="/api/v2")
router.include_router(sessions.router)
router.include_router(llm_traces.router)
router.include_router(events.router)
router.include_router(middleware.router)

__all__ = ["router"]
