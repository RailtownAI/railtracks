"""Session events: the classes themselves, and the hot-path emission for a top-level
`rt.call` or `rt.astream`.

The hot-path tests run a real graph through `Flow`/`Session`/`rt.astream` and assert that
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
from railtracks.exceptions import FatalError, GlobalTimeOutError, LLMError
from railtracks.observability import Event, configure_writers


class _Collecting:
    def __init__(self):
        self.events: list[Event] = []

    def start(self):
        pass

    def write(self, event: Event):
        self.events.append(event)

    def shutdown(self):
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


@rt.function_node
def stop(x: int) -> int:
    """Stops the run."""
    raise FatalError("cannot continue")


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


@pytest.mark.parametrize(
    ("node", "end_on_error", "fatal"),
    [(boom, False, False), (boom, True, True), (stop, False, True)],
)
async def test_completed_marks_a_failure_that_stops_the_run(
    writer, node, end_on_error, fatal
):
    with rt.Session(flow_name="f", end_on_error=end_on_error):
        with pytest.raises((ValueError, FatalError)):
            await rt.call(node, 1)

    completed = _of_type(writer.events, "session.completed")
    assert completed[0].payload["fatal"] is fatal


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


def _streamer(llm):
    return rt.agent_node(name="Streamer", system_message="stream", llm=llm)


async def test_a_top_level_stream_is_bracketed_by_session_events(writer, mock_llm):
    final = await rt.astream(_streamer(mock_llm(custom_response="Echo")), "go")
    assert final.text == "Echo"

    assert writer.events[0].event_type == "session.started"
    assert writer.events[-1].event_type == "session.completed"
    assert writer.events[0].payload["entry_point_name"] == "Streamer"
    assert writer.events[-1].payload["status"] == "success"


async def test_a_failed_top_level_stream_still_reports_completed(writer, mock_llm):
    class _FailingLLM(mock_llm):
        async def _astream_chat(self, messages, **kwargs):
            yield "a"
            raise RuntimeError("boom mid-stream")

    with pytest.raises(LLMError):
        await rt.astream(_streamer(_FailingLLM()), "go")

    completed = _of_type(writer.events, "session.completed")
    assert len(completed) == 1
    assert completed[0].payload["status"] == "failure"


async def test_a_timed_out_top_level_stream_reports_the_timeout(writer, mock_llm):
    class _SlowLLM(mock_llm):
        async def _astream_chat(self, messages, **kwargs):
            await asyncio.sleep(0.5)
            yield "too late"

    with rt.Session(flow_name="f", timeout=0.1):
        with pytest.raises(GlobalTimeOutError):
            await rt.astream(_streamer(_SlowLLM()), "go")

    completed = _of_type(writer.events, "session.completed")[0]
    assert completed.payload["status"] == "failure"
    assert "timed out" in completed.payload["error"]


async def test_a_stream_inside_a_node_is_part_of_its_callers_run(writer, mock_llm):
    agent = _streamer(mock_llm(custom_response="Echo"))

    @rt.function_node
    async def entry() -> str:
        """Streams the agent."""
        return (await rt.astream(agent, "go")).text

    assert await rt.Flow("f", entry).ainvoke() == "Echo"

    assert len(_of_type(writer.events, "session.started")) == 1
    assert len(_of_type(writer.events, "session.completed")) == 1
