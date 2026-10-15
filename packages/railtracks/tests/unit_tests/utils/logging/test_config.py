import io
import logging
import os
import sys
import tempfile
from unittest.mock import patch

import pytest
import railtracks as rt
from railtracks.observability import configure
from railtracks.utils.logging import config, run_view, setup
from railtracks.utils.logging.config import (
    LifecycleFilter,
    RichConsoleHandler,
    ThreadAwareFilter,
    _module_logging_level,
    _short_suffix_label,
    detach_logging_handlers,
    lifecycle_logger_name,
    rt_logger,
    run_view_level,
    setup_file_handler,
)
from railtracks.utils.logging.setup import enable_logging, initialize_module_logging
from rich.console import Console

# ================= RichConsoleHandler Tests =================


def _record(
    name: str = "RT.railtracks.state.state", level: int = logging.INFO, **extra
) -> logging.LogRecord:
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="",
        lineno=0,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    record.__dict__.update(extra)
    return record


@pytest.fixture
def console_output(monkeypatch) -> io.StringIO:
    buffer = io.StringIO()
    monkeypatch.setattr(
        config, "console", Console(file=buffer, width=200, color_system=None)
    )
    return buffer


def test_short_suffix_label_strips_leading_underscores():
    assert _short_suffix_label("_session") == "Session"
    assert _short_suffix_label("state") == "State"


@pytest.mark.parametrize(
    ("name", "name_style", "level", "expected"),
    [
        (
            "RT.railtracks._session",
            "short",
            logging.WARNING,
            "RT.Session  : WARNING  - hello world",
        ),
        (
            "RT.railtracks.state.state",
            "short",
            logging.ERROR,
            "RT.State    : ERROR    - hello world",
        ),
        ("RT", "short", logging.DEBUG, "RT          : DEBUG    - hello world"),
        (
            "RT.railtracks.state.state",
            "full",
            logging.WARNING,
            "RT.railtracks.state.state: WARNING  - hello world",
        ),
        ("RT.railtracks._session", "short", logging.INFO, "· hello world"),
        ("RT.railtracks.state.state", "full", logging.INFO, "· hello world"),
    ],
)
def test_console_handler_line_layout(console_output, name, name_style, level, expected):
    RichConsoleHandler(name_style=name_style).emit(_record(name, level))

    assert console_output.getvalue().rstrip("\n").endswith(f"] {expected}")


def test_console_handler_leaves_no_custom_attributes_on_the_record(console_output):
    """Handlers further up the tree (e.g. a log shipper on root) see the record as logged."""
    record = _record()
    before = set(record.__dict__)

    RichConsoleHandler().emit(record)

    assert set(record.__dict__) - before <= {"message"}


def test_console_handler_includes_the_traceback(console_output):
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record()
        record.exc_info = sys.exc_info()

    RichConsoleHandler().emit(record)

    assert "ValueError: boom" in console_output.getvalue()


def test_lifecycle_filter_drops_only_records_of_runs_the_view_shows():
    lifecycle_filter = LifecycleFilter(lambda session_id: session_id == "shown")

    shown = _record(lifecycle_logger_name, session_id="shown")
    assert lifecycle_filter.filter(shown) is False
    assert lifecycle_filter.filter(_record(lifecycle_logger_name, session_id="other"))
    assert lifecycle_filter.filter(_record(lifecycle_logger_name))
    assert lifecycle_filter.filter(_record(session_id="shown"))


def test_lifecycle_records_still_reach_other_handlers(console_output, monkeypatch):
    """The filter sits on railtracks' console handler, not the logger."""
    monkeypatch.setattr(setup._run_view, "is_showing", lambda session_id: True)
    detach_logging_handlers()
    enable_logging(level="INFO")
    captured: list[logging.LogRecord] = []
    other = logging.Handler()
    other.emit = captured.append
    rt_logger.addHandler(other)

    logging.getLogger(lifecycle_logger_name).info("A CREATED B")

    assert [r.getMessage() for r in captured] == ["A CREATED B"]
    assert console_output.getvalue() == ""
    detach_logging_handlers()


def test_the_console_prints_lifecycle_records_only_for_runs_the_view_is_not_showing(
    console_output, monkeypatch
):
    monkeypatch.setattr(run_view, "console", config.console)
    detach_logging_handlers()
    enable_logging(level="INFO")

    def boom(text: str) -> str:
        """Fail.

        Args:
            text: The text.
        """
        raise ValueError("bad")

    with pytest.raises(ValueError):
        rt.Flow(name="Boom Flow", entry_point=rt.function_node(boom)).invoke("x")
    # e.g. a task still running after its run ended
    logging.getLogger(lifecycle_logger_name).error(
        "late FAILED", extra={"session_id": "ended"}
    )

    output = console_output.getvalue()
    assert "✗ boom failed: ValueError: bad" in output
    assert "boom FAILED" not in output
    assert "late FAILED" in output
    detach_logging_handlers()


def test_console_writes_to_stderr_in_a_terminal():
    assert config._make_console().stderr is True


def test_console_writes_ansi_to_stdout_in_a_notebook(monkeypatch):
    """Rich would send each line as its own HTML output; one ANSI stream reads as a block."""
    monkeypatch.setattr("rich.console._is_jupyter", lambda: True)

    notebook_console = config._make_console()

    assert notebook_console.is_jupyter is False
    assert notebook_console.is_terminal is True
    assert notebook_console.file is sys.stdout


# ================= run_view_level Tests =================


def test_run_view_level_is_none_until_the_console_is_enabled():
    detach_logging_handlers()

    assert run_view_level() is None


def test_run_view_level_prefers_the_thread_level():
    detach_logging_handlers()
    enable_logging(level="INFO")
    token = _module_logging_level.set(logging.DEBUG)
    try:
        assert run_view_level() == logging.DEBUG
    finally:
        _module_logging_level.reset(token)

    token = _module_logging_level.set(None)
    try:
        assert run_view_level() == logging.INFO
    finally:
        _module_logging_level.reset(token)
    detach_logging_handlers()


def test_run_view_level_is_none_once_the_console_handler_is_removed():
    """Someone swapping railtracks' console for their own handler turns the view off."""
    detach_logging_handlers()
    enable_logging(level="INFO")

    rt_logger.handlers.clear()

    assert run_view_level() is None


# ================= ThreadAwareFilter Tests =================


def test_thread_aware_filter_passes_when_level_met():
    """Test that ThreadAwareFilter allows records that meet the thread's log level."""
    filter_instance = ThreadAwareFilter()
    _module_logging_level.set(logging.INFO)

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test message",
        args=(),
        exc_info=None,
    )

    assert filter_instance.filter(record) is True


def test_thread_aware_filter_blocks_when_level_not_met():
    """Test that ThreadAwareFilter blocks records below the thread's log level."""
    filter_instance = ThreadAwareFilter()
    _module_logging_level.set(logging.WARNING)

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test message",
        args=(),
        exc_info=None,
    )

    assert filter_instance.filter(record) is False


def test_thread_aware_filter_allows_all_when_level_none():
    """Test that ThreadAwareFilter allows all records when thread level is None."""
    filter_instance = ThreadAwareFilter()
    _module_logging_level.set(None)

    record = logging.LogRecord(
        name="test",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="test message",
        args=(),
        exc_info=None,
    )

    assert filter_instance.filter(record) is True


# ================= setup_file_handler Tests =================


def test_setup_file_handler_creates_handler(tmp_path):
    """Test that setup_file_handler creates and adds a file handler."""
    log_file = tmp_path / "test.log"
    initial_handler_count = len(rt_logger.handlers)

    setup_file_handler(file_name=log_file)

    assert len(rt_logger.handlers) == initial_handler_count + 1
    # Clean up
    rt_logger.handlers.clear()


def test_setup_file_handler_with_custom_level(tmp_path):
    """Test that setup_file_handler respects custom logging level."""
    log_file = tmp_path / "test.log"

    setup_file_handler(file_name=log_file, file_logging_level=logging.DEBUG)

    file_handler = rt_logger.handlers[-1]
    assert file_handler.level == logging.DEBUG
    # Clean up
    rt_logger.handlers.clear()


# ================= detach_logging_handlers Tests =================


def test_detach_logging_handlers_clears_all_handlers():
    """Test that detach_logging_handlers removes all handlers."""
    # Add some handlers
    rt_logger.addHandler(logging.StreamHandler())
    rt_logger.addHandler(logging.NullHandler())

    detach_logging_handlers()

    assert len(rt_logger.handlers) == 0


# ================= enable_logging Tests =================


def test_enable_logging_adds_real_handlers():
    """Test that enable_logging() (opt-in API) adds railtracks' console handler."""
    detach_logging_handlers()

    enable_logging(level="INFO")

    console_handlers = [
        h for h in rt_logger.handlers if isinstance(h, RichConsoleHandler)
    ]
    assert len(console_handlers) == 1, (
        "enable_logging() should add railtracks' console handler"
    )

    detach_logging_handlers()


def test_enable_logging_registers_the_run_view(monkeypatch):
    """Logging registers its own run view with observability; core doesn't wire it."""
    monkeypatch.setattr(configure, "_inline_listeners", [])
    detach_logging_handlers()

    enable_logging(level="INFO")

    assert configure.inline_listeners() == [setup._run_view.record]
    detach_logging_handlers()


# ================= initialize_module_logging Tests =================


@patch.dict(os.environ, {"RT_LOG_LEVEL": "DEBUG"}, clear=False)
def test_initialize_module_logging_reads_env_level():
    """Test that initialize_module_logging reads RT_LOG_LEVEL from environment."""
    # Clear handlers first
    detach_logging_handlers()
    _module_logging_level.set(None)

    initialize_module_logging()

    # Verify the context var was set correctly
    assert _module_logging_level.get() == logging.DEBUG

    # Clean up
    detach_logging_handlers()


@patch.dict(
    os.environ,
    {"RT_LOG_FILE": os.path.join(tempfile.gettempdir(), "test.log")},
    clear=False,
)
def test_initialize_module_logging_reads_env_file():
    """Test that initialize_module_logging reads RT_LOG_FILE from environment."""
    from railtracks.utils.logging.config import _module_logging_file

    detach_logging_handlers()

    initialize_module_logging()

    assert _module_logging_file.get().endswith("test.log")
    detach_logging_handlers()


@patch.dict(os.environ, {}, clear=True)
def test_initialize_module_logging_defaults_to_info():
    """Test that initialize_module_logging defaults to INFO level."""
    # Clear RT_LOG_LEVEL if it exists
    os.environ.pop("RT_LOG_LEVEL", None)
    os.environ.pop("RT_LOG_FILE", None)

    # Clear handlers first
    detach_logging_handlers()
    _module_logging_level.set(None)

    initialize_module_logging()

    # Verify the context var was set to INFO
    assert _module_logging_level.get() == logging.INFO

    # Clean up
    detach_logging_handlers()
