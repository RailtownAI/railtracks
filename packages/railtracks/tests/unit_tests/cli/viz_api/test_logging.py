from __future__ import annotations

import json
import logging

from railtracks.cli.viz_api._logging import _JsonFormatter


def test_structured_formatter_emits_event_fields_as_json() -> None:
    record = logging.LogRecord(
        name="railtracks.viz_api",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=1,
        msg="query_completed",
        args=(),
        exc_info=None,
    )
    record.event = "query_completed"  # type: ignore[attr-defined]
    record.fields = {  # type: ignore[attr-defined]
        "query": "list_session_rows",
        "rows": 50,
        "duration_ms": 1.25,
    }

    payload = json.loads(_JsonFormatter().format(record))

    assert payload["level"] == "debug"
    assert payload["event"] == "query_completed"
    assert payload["query"] == "list_session_rows"
    assert payload["rows"] == 50
    assert payload["duration_ms"] == 1.25
