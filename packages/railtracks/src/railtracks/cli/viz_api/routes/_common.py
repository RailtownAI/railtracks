"""Shared helpers for the route modules."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRoute
from railtracks.paths import resolve_railtracks_home
from railtracks.query import EventQuery

from ...io import print_error
from .. import queries

_EVENTS_SUBDIR = "data/new-ones"

#: UUID-shape pattern applied to ``{session_id}`` so the sibling literals
#: ``/sessions/stats`` and ``/sessions/filters`` are not swallowed as ids.
_SESSION_ID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _events_dir() -> Path:
    return resolve_railtracks_home() / _EVENTS_SUBDIR


def get_query_or_none() -> EventQuery | None:
    """FastAPI dependency: shared query connection, or ``None`` if no events home.

    Used by list/stats/filter endpoints, which return an empty payload rather
    than a 404 when nothing has been recorded yet.
    """
    d = _events_dir()
    if not d.exists():
        return None
    return queries.get_query(d)


def get_query_or_404() -> EventQuery:
    """FastAPI dependency: shared query connection, or raises 404.

    Used by detail endpoints, where "no events home" is not a valid state to
    answer from.
    """
    d = _events_dir()
    if not d.exists():
        raise HTTPException(status_code=404, detail="no events home")
    return queries.get_query(d)


class QueryFailureRoute(APIRoute):
    """Route class that turns any unhandled query exception into a logged 500.

    Applied at the sub-router level so every endpoint shares one policy — a
    query that raises reports a clean error to the client instead of leaking
    the traceback into the response body, and the traceback message lands in
    the server log for the next reader.
    """

    def get_route_handler(self) -> Callable[[Request], Any]:
        original = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await original(request)
            except HTTPException:
                raise
            except Exception as e:  # noqa: BLE001
                print_error(f"{request.url.path} query failed: {e}")
                raise HTTPException(
                    status_code=500, detail="failed to query events"
                ) from e

        return wrapped
