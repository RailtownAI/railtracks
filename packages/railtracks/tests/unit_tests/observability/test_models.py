from datetime import datetime, timezone

from railtracks.observability import (
    SCOPE_EVALUATION,
    SCOPE_RETRIEVAL,
    SCOPE_SESSION,
    Event,
    Stamp,
)


def test_stamp_now_returns_tz_aware_utc_datetime():
    stamp = Stamp.now()
    assert isinstance(stamp, datetime)
    assert stamp.tzinfo is not None
    assert stamp.utcoffset() == timezone.utc.utcoffset(stamp)


def test_event_defaults():
    event = Event(
        event_type="llm.call",
        stamp=Stamp.now(),
        scope_type=SCOPE_SESSION,
        scope_id="s1",
    )
    assert event.event_id
    assert event.parent_scope_id is None
    assert event.payload == {}


def test_event_ids_are_unique_by_default():
    a = Event(event_type="x", stamp=Stamp.now(), scope_type=SCOPE_SESSION, scope_id="s1")
    b = Event(event_type="x", stamp=Stamp.now(), scope_type=SCOPE_SESSION, scope_id="s1")
    assert a.event_id != b.event_id


def test_event_json_round_trip():
    event = Event(
        event_type="tool.invoke",
        stamp=Stamp.now(),
        scope_type=SCOPE_RETRIEVAL,
        scope_id="r1",
        parent_scope_id="s1",
        payload={"tool": "search", "args": {"q": "hello"}},
    )
    parsed = Event.model_validate_json(event.model_dump_json())
    assert parsed == event


def test_event_type_accepts_arbitrary_strings():
    Event(
        event_type="totally.made.up.event",
        stamp=Stamp.now(),
        scope_type=SCOPE_EVALUATION,
        scope_id="e1",
    )


def test_scope_constants():
    assert SCOPE_SESSION == "session"
    assert SCOPE_RETRIEVAL == "retrieval"
    assert SCOPE_EVALUATION == "evaluation"
