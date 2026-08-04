"""Session events: the classes themselves, and the hot-path emission in `_call.py::_start`.

The hot-path tests run a real graph through `Flow`/`Session` and assert that
`session.started` opens the run and `session.completed` closes it, on both the success
and the failure path.
"""

import asyncio

import pytest
import railtracks as rt
from railtracks.events._base import NoSpatialParent
from railtracks.events.session import (
    SessionCompleted,
    SessionStarted,
    format_error,
)
from railtracks.exceptions import GlobalTimeOutError
from railtracks.observability import Event, configure, configure_writers


class _Collecting:
    def __init__(self):
        self.events: list[Event] = []

    async def start(self):
        pass

    async def write(self, event: Event):
        self.events.append(event)

    async def shutdown(self):
        pass


@pytest.fixture
def writer():
    """A collecting writer registered on a fresh observer.

    `_start` shuts the singleton observer down at the end of every top-level call, so a
    test that runs a second flow needs a fresh one; that is what `reset_for_tests` in the
    package `conftest` gives us between tests.
    """
    w = _Collecting()
    configure_writers([w])
    return w


def _of_type(events, event_type):
    return [e for e in events if e.event_type == event_type]


def _session_events(events):
    return [e for e in events if e.event_type.startswith("session.")]


@rt.function_node
def add_one(x: int) -> int:
    """Adds one."""
    return x + 1


@rt.function_node
def boom(x: int) -> int:
    """Explodes."""
    raise ValueError("kaboom")


# ── The event classes ────────────────────────────────────────────────────────


def _started_kwargs():
    return {
        "session_id": "sess-1",
        "flow_name": "flow",
        "flow_id": "fid",
        "session_name": None,
        "entry_point_name": "Agent",
        "timeout": 150.0,
        "end_on_error": False,
        "save_state": True,
    }


def test_event_type_strings():
    assert SessionStarted(**_started_kwargs()).event_type() == "session.started"
    assert (
        SessionCompleted(
            session_id="sess-1", status="success", error=None, duration_seconds=0.1
        ).event_type()
        == "session.completed"
    )


def test_session_events_are_the_root_of_the_tree():
    # a session event is emitted outside every node/middleware/llm scope, so there is
    # nothing above it to resolve — with or without an ambient chain.
    ev = SessionStarted(**_started_kwargs())
    assert ev._get_spatial_parent(None) == NoSpatialParent()

    ev.resolve_relationships(None)
    assert ev.spatial_parent == NoSpatialParent()
    ev.verify()  # every field populated: nothing left UNSET


def test_format_error_strips_terminal_colors():
    # RT's own exceptions colorize __str__; the payload should stay clean text
    assert format_error(GlobalTimeOutError(timeout=0.5)) == (
        "Execution timed out after 0.5 seconds"
    )
    assert format_error(ValueError("kaboom")) == "kaboom"


# ── Hot path ─────────────────────────────────────────────────────────────────


async def test_success_run_is_bracketed_by_session_events(writer):
    result = await rt.Flow("my-flow", add_one).ainvoke(10)
    assert result == 11

    # the pair brackets the whole run: nothing is emitted before started or after completed
    assert writer.events[0].event_type == "session.started"
    assert writer.events[-1].event_type == "session.completed"
    assert len(_session_events(writer.events)) == 2

    started = writer.events[0]
    completed = writer.events[-1]

    # the event is scoped to the session, and carries that identity in the payload too
    assert started.scope_type == "session"
    assert started.payload["session_id"] == started.scope_id
    assert completed.payload["session_id"] == started.scope_id

    assert started.payload["flow_name"] == "my-flow"
    assert started.payload["flow_id"] is not None
    assert started.payload["session_name"] is None
    assert started.payload["entry_point_name"] == "add_one"
    # the effective config the run executed under
    assert started.payload["end_on_error"] is False

    assert completed.payload["status"] == "success"
    assert completed.payload["error"] is None
    assert completed.payload["duration_seconds"] >= 0


async def test_session_name_and_flow_name_come_from_a_bare_session(writer):
    with rt.Session(flow_name="f", name="named-session"):
        await rt.call(add_one, 1)

    started = _of_type(writer.events, "session.started")[0]
    assert started.payload["flow_name"] == "f"
    assert started.payload["session_name"] == "named-session"
    # flow_id is only set by Flow
    assert started.payload["flow_id"] is None


async def test_failed_run_still_reports_completed(writer):
    with rt.Session(flow_name="f"):
        with pytest.raises(ValueError):
            await rt.call(boom, 1)

    completed = _of_type(writer.events, "session.completed")
    assert len(completed) == 1
    assert completed[0].payload["status"] == "failure"
    assert completed[0].payload["error"] == "kaboom"

    # the observer is torn down on the failure path too, so writers get drained
    assert configure.observer._running is False


async def test_global_timeout_reports_the_timeout_error(writer):
    @rt.function_node
    async def slow(x: int) -> int:
        """Takes too long."""
        await asyncio.sleep(5)
        return x

    with rt.Session(flow_name="f", timeout=0.2):
        with pytest.raises(GlobalTimeOutError):
            await rt.call(slow, 1)

    started = _of_type(writer.events, "session.started")[0]
    assert started.payload["timeout"] == 0.2

    completed = _of_type(writer.events, "session.completed")[0]
    assert completed.payload["status"] == "failure"
    assert "timed out" in completed.payload["error"]
