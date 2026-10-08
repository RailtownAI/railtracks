"""The console run view, fed session events directly."""

import io
import logging
import re

import pytest
import railtracks as rt
from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.observability import Event
from railtracks.utils.logging import config, run_view
from railtracks.utils.logging.run_view import RunView
from rich.console import Console

SESSION = "sess-1"
ENTRY = "node-entry"
CHILD = "node-child"
LLM_CALL = "llm-invoke-1"
MIDDLEWARE_CALL = "mw-invoke-1"


@pytest.fixture
def output(monkeypatch) -> io.StringIO:
    buffer = io.StringIO()
    monkeypatch.setattr(
        run_view, "console", Console(file=buffer, width=200, color_system=None)
    )
    return buffer


@pytest.fixture
def level(monkeypatch):
    """Sets the level the next run starts at."""

    def set_level(value: int | None) -> None:
        monkeypatch.setattr(run_view, "run_view_level", lambda: value)

    set_level(logging.INFO)
    return set_level


def _event(event_type: str, session: str = SESSION, **payload) -> Event:
    return Event(
        event_type=event_type, scope_type="session", scope_id=session, payload=payload
    )


def _started(session: str = SESSION, end_on_error: bool = False) -> Event:
    return _event(
        "session.started",
        session=session,
        flow_name="My Flow",
        session_name=None,
        entry_point_name="Entry",
        end_on_error=end_on_error,
    )


def _completed(status: str = "success", error: str | None = None) -> Event:
    return _event("session.completed", status=status, error=error, duration_seconds=0.5)


def _node_started(node_id: str, name: str, caller: str | None) -> list[Event]:
    return [
        _event("node.creation", node_id=node_id, name=name, node_type="Tool"),
        _event(
            "node.invocation",
            parent_node_id=node_id,
            spatial_parent_type="node",
            spatial_parent_node_id=caller,
            args=("hi",),
            kwargs={"n": 2},
        ),
    ]


def _node_done(node_id: str, response="ok") -> Event:
    return _event(
        "node.destruction",
        parent_node_id=node_id,
        response=response,
        duration_seconds=0.25,
    )


def _feed(view: RunView, *events: Event | list[Event]) -> None:
    for item in events:
        for event in item if isinstance(item, list) else [item]:
            view.record(event)


def _lines(output: io.StringIO) -> list[str]:
    # drop the "[+  0.000s] " clock so assertions read the content and its indentation
    return [
        re.sub(r"^\[\+\s*[\d.]+s\] ", "", line)
        for line in output.getvalue().splitlines()
    ]


def test_nested_nodes_indent_under_their_caller(output, level):
    _feed(
        RunView(),
        _started(),
        _node_started(ENTRY, "Entry", caller=None),
        _node_started(CHILD, "Child", caller=ENTRY),
        _node_done(CHILD),
        _node_done(ENTRY),
        _completed(),
    )

    assert _lines(output) == [
        "▶ My Flow  entry: Entry",
        "  ▶ Entry",
        "    ▶ Child",
        "    ✓ Child 0.250s",
        "  ✓ Entry 0.250s",
        "✓ My Flow in 0.500s",
    ]


def test_warning_shows_only_the_run_and_failures(output, level):
    level(logging.WARNING)
    _feed(
        RunView(),
        _started(),
        _node_started(ENTRY, "Entry", caller=None),
        _event(
            "node.failure",
            parent_node_id=ENTRY,
            exception_name="ValueError",
            exception_message="bad",
            fatal=False,
        ),
        _node_done(ENTRY, response=None),
        _completed(status="failure", error="bad"),
    )

    assert _lines(output) == [
        "▶ My Flow  entry: Entry",
        "  ✗ Entry failed: ValueError: bad",
        "✗ My Flow failed in 0.500s: bad",
    ]


def test_debug_adds_arguments_and_responses(output, level):
    level(logging.DEBUG)
    _feed(
        RunView(),
        _started(),
        _node_started(ENTRY, "Entry", caller=None),
        _node_done(ENTRY, response=42),
    )

    assert _lines(output)[1:] == [
        "  ▶ Entry ('hi', n=2)",
        "  ✓ Entry 0.250s → 42",
    ]


def test_long_values_are_truncated(output, level):
    level(logging.DEBUG)
    _feed(
        RunView(),
        _started(),
        _node_started(ENTRY, "Entry", caller=None),
        _node_done(ENTRY, response="x" * 500),
    )

    done = _lines(output)[-1]
    assert done.endswith("…")
    assert len(done) < 200


@pytest.mark.parametrize(
    ("fatal", "end_on_error", "marked"),
    [(True, False, True), (False, True, True), (False, False, False)],
)
def test_failure_is_marked_fatal_when_it_stops_the_run(
    output, level, fatal, end_on_error, marked
):
    _feed(
        RunView(),
        _started(end_on_error=end_on_error),
        _node_started(ENTRY, "Entry", caller=None),
        _event(
            "node.failure",
            parent_node_id=ENTRY,
            exception_name="FatalError",
            exception_message="stop",
            fatal=fatal,
        ),
    )

    assert _lines(output)[-1].endswith("(fatal)") is marked


def test_llm_call_nests_under_its_node_with_its_stats(output, level):
    view = RunView()
    # a model announces itself once; a later run still knows its name
    _feed(view, _event("llm.creation", llm_id="model-1", model_name="claude-x"))
    _feed(
        view,
        _started(),
        _node_started(ENTRY, "Entry", caller=None),
        _event(
            "llm.response",
            spatial_parent_node_id=ENTRY,
            parent_llm_invoke_id=LLM_CALL,
            parent_llm_type_id="model-1",
            reported_model_name=None,
            input_tokens=120,
            output_tokens=30,
            total_cost=0.0021,
            latency=0.8,
        ),
    )

    assert _lines(output)[-1] == "    ◆ claude-x 120→30 tokens · $0.0021 · 0.80s"


def test_guardrail_decision_shows_at_debug(output, level):
    level(logging.DEBUG)
    view = RunView()
    _feed(
        view,
        _event("middleware.creation", middleware_type_id="mw-1", middleware_name="PII"),
        _started(),
        _node_started(ENTRY, "Entry", caller=None),
        _event(
            "llm.invocation",
            spatial_parent_node_id=ENTRY,
            parent_llm_invoke_id=LLM_CALL,
        ),
        _event(
            "middleware.guard.input.response",
            spatial_parent_llm_invoke_id=LLM_CALL,
            parent_middleware_type_id="mw-1",
            parent_middleware_invoke_id=MIDDLEWARE_CALL,
            decision=GuardrailDecision.block(reason="found an email"),
        ),
    )

    assert _lines(output)[-1] == "    · PII → block (found an email)"


def test_middleware_passing_an_exception_through_prints_nothing(output, level):
    _feed(
        RunView(),
        _started(),
        _node_started(ENTRY, "Entry", caller=None),
        _event(
            "middleware.failure",
            spatial_parent_node_id=ENTRY,
            parent_middleware_type_id="mw-1",
            parent_middleware_invoke_id=MIDDLEWARE_CALL,
            exception_name="ValueError",
            exception_message="bad",
        ),
    )

    assert len(_lines(output)) == 2


def _llm_done(node_id: str, invoke_id: str, tokens: int) -> Event:
    return _event(
        "llm.response",
        spatial_parent_node_id=node_id,
        parent_llm_invoke_id=invoke_id,
        parent_llm_type_id="model-1",
        reported_model_name="gpt",
        input_tokens=tokens,
        output_tokens=1,
        total_cost=None,
        latency=None,
    )


def test_siblings_running_at_once_name_their_branch(output, level):
    """An orchestrator calls two agents in one turn, and their lines interleave."""
    analyst, poet, tool = "node-analyst", "node-poet", "node-tool"
    _feed(
        RunView(),
        _started(),
        _node_started(ENTRY, "Orchestrator", caller=None),
        _node_started(analyst, "Word Analyst", caller=ENTRY),
        _node_started(poet, "Poet", caller=ENTRY),
        _llm_done(analyst, "llm-a1", tokens=199),
        _node_started(tool, "count_letters", caller=analyst),
        _node_done(tool),
        _llm_done(poet, "llm-p1", tokens=47),
        _node_done(poet),
        # the poet is done, but the analyst's remaining lines still need its name
        _llm_done(analyst, "llm-a2", tokens=234),
        _node_done(analyst),
        _llm_done(ENTRY, "llm-o2", tokens=311),
        _node_done(ENTRY),
    )

    assert _lines(output)[1:] == [
        "  ▶ Orchestrator",
        "    ▶ Word Analyst",
        "    ▶ Poet",
        "      Word Analyst › ◆ gpt 199→1 tokens",
        "      Word Analyst › ▶ count_letters",
        "      Word Analyst › ✓ count_letters 0.250s",
        "      Poet › ◆ gpt 47→1 tokens",
        "    ✓ Poet 0.250s",
        "      Word Analyst › ◆ gpt 234→1 tokens",
        "    ✓ Word Analyst 0.250s",
        "    ◆ gpt 311→1 tokens",
        "  ✓ Orchestrator 0.250s",
    ]


def test_node_called_from_middleware_nests_under_that_middleware_node(output, level):
    view = RunView()
    _feed(
        view,
        _started(),
        _node_started(ENTRY, "Entry", caller=None),
        _event(
            "middleware.invocation",
            spatial_parent_node_id=ENTRY,
            parent_middleware_type_id="mw-1",
            parent_middleware_invoke_id=MIDDLEWARE_CALL,
            args=(),
            kwargs={},
        ),
        _event("node.creation", node_id=CHILD, name="Judge", node_type="Agent"),
        _event(
            "node.invocation",
            parent_node_id=CHILD,
            spatial_parent_type="middleware",
            spatial_parent_middleware_invoke_id=MIDDLEWARE_CALL,
            args=(),
            kwargs={},
        ),
    )

    assert _lines(output)[-1] == "    ▶ Judge"


def test_nothing_prints_when_the_console_is_not_enabled(output, level):
    level(None)
    _feed(RunView(), _started(), _node_started(ENTRY, "Entry", caller=None))

    assert output.getvalue() == ""


def test_each_run_keeps_the_level_it_started_with(output, level):
    view = RunView()
    level(logging.WARNING)
    _feed(view, _started(session="quiet"))
    level(logging.INFO)
    _feed(view, _started(session="chatty"))

    for session in ("quiet", "chatty"):
        _feed(
            view,
            _event(
                "node.creation",
                session=session,
                node_id=session,
                name=session,
                node_type="Tool",
            ),
            _event(
                "node.invocation",
                session=session,
                parent_node_id=session,
                spatial_parent_type="node",
                spatial_parent_node_id=None,
                args=(),
                kwargs={},
            ),
        )

    assert "  ▶ chatty" in _lines(output)
    assert "  ▶ quiet" not in _lines(output)


def test_run_state_is_dropped_when_the_run_completes(output, level):
    view = RunView()
    _feed(view, _started(), _completed())

    assert view._runs == {}


def test_a_flow_prints_through_the_session_listener(monkeypatch, output):
    """End to end: a real run reaches the view through the session's inline listener."""
    monkeypatch.setattr(config, "_console_level", logging.INFO)
    # other tests leave a thread level behind; this run should use the console's
    token = config._module_logging_level.set(None)

    def shout(text: str) -> str:
        """Shout.

        Args:
            text: The text.
        """
        return text.upper()

    flow = rt.Flow(name="Shout Flow", entry_point=rt.function_node(shout))
    try:
        assert flow.invoke("hi") == "HI"
    finally:
        config._module_logging_level.reset(token)

    lines = _lines(output)
    assert lines[0] == "▶ Shout Flow  entry: shout"
    assert lines[1] == "  ▶ shout"
    assert lines[2].startswith("  ✓ shout ")
    assert lines[3].startswith("✓ Shout Flow in ")
