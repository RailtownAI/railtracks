from datetime import datetime, timezone

from railtracks.observability import (
    SCOPE_EVALUATION,
    SCOPE_RETRIEVAL,
    SCOPE_SESSION,
    Event,
    Timestamp,
)


def test_stamp_now_returns_tz_aware_utc_datetime():
    stamp = Timestamp.now()
    assert isinstance(stamp, datetime)
    assert stamp.tzinfo is not None
    assert stamp.utcoffset() == timezone.utc.utcoffset(stamp)


def test_event_defaults():
    event = Event(
        event_type="llm.call",
        stamp=Timestamp.now(),
        scope_type=SCOPE_SESSION,
        scope_id="s1",
    )
    assert event.event_id
    assert event.parent_scope_id is None
    assert event.payload == {}


def test_event_ids_are_unique_by_default():
    a = Event(event_type="x", stamp=Timestamp.now(), scope_type=SCOPE_SESSION, scope_id="s1")
    b = Event(event_type="x", stamp=Timestamp.now(), scope_type=SCOPE_SESSION, scope_id="s1")
    assert a.event_id != b.event_id


def test_event_type_accepts_arbitrary_strings():
    Event(
        event_type="totally.made.up.event",
        stamp=Timestamp.now(),
        scope_type=SCOPE_EVALUATION,
        scope_id="e1",
    )


def test_scope_constants():
    assert SCOPE_SESSION == "session"
    assert SCOPE_RETRIEVAL == "retrieval"
    assert SCOPE_EVALUATION == "evaluation"
