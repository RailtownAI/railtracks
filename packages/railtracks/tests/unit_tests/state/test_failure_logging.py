"""The log records a run sends through stdlib ``logging``.

Log shippers attached to the root logger (``railtownai``, for one) turn these records
into errors on their side, so their level, traceback, and ids are a contract.
"""

import logging

import pytest
import railtracks as rt


def boom(text: str) -> str:
    """Fail.

    Args:
        text: The text.
    """
    raise ValueError(f"cannot handle {text!r}")


def echo(text: str) -> str:
    """Echo.

    Args:
        text: The text.
    """
    return text


def _rt_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name.startswith("RT")]


def test_node_failure_is_an_error_record_with_traceback_and_ids(caplog):
    flow = rt.Flow(name="Boom Flow", entry_point=rt.function_node(boom))

    with caplog.at_level(logging.INFO, logger="RT"):
        with pytest.raises(ValueError):
            flow.invoke("x")

    failures = [r for r in _rt_records(caplog) if r.levelno >= logging.ERROR]
    assert [r.getMessage() for r in failures] == ["boom FAILED"]
    failure = failures[0]
    assert failure.exc_info is not None
    assert isinstance(failure.exc_info[1], ValueError)
    assert failure.session_id is not None
    # logged from the state handler rather than inside the node, so these are not
    # populated yet; the keys are still part of every record
    assert hasattr(failure, "node_id")
    assert hasattr(failure, "run_id")
    # the run view prints failures, so railtracks' console skips this record; handlers
    # like a log shipper's still receive it
    assert failure.rt_lifecycle is True


def test_created_and_done_records_are_marked_as_lifecycle(caplog):
    flow = rt.Flow(name="Echo Flow", entry_point=rt.function_node(echo))

    with caplog.at_level(logging.INFO, logger="RT"):
        flow.invoke("x")

    lifecycle = {
        r.getMessage() for r in _rt_records(caplog) if getattr(r, "rt_lifecycle", False)
    }
    assert lifecycle == {"START CREATED echo", "echo DONE"}
