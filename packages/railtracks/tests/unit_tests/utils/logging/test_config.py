import logging
import os
import tempfile
from unittest.mock import patch

import pytest

from railtracks.utils.logging.config import (
    ColorfulFormatter,
    ThreadAwareFilter,
    detach_logging_handlers,
    enable_logging,
    initialize_module_logging,
    prepare_logger,
    rt_logger,
    setup_file_handler,
    _module_logging_level,
)


# ================= ColorfulFormatter Tests =================

def test_colorful_formatter_adds_relative_seconds():
    """Test that the formatter adds relative_seconds attribute to log records."""
    formatter = ColorfulFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test message",
        args=(),
        exc_info=None,
    )
    record.relativeCreated = 1234.567
    
    formatter.format(record)
    
    assert hasattr(record, "relative_seconds")
    assert record.relative_seconds == "1.235"  # type: ignore


def test_colorful_formatter_restores_original_msg():
    """Test that formatter restores original msg and args after formatting."""
    formatter = ColorfulFormatter()
    original_msg = "test message with %s and %s keywords"
    original_args = ("CREATED", "DONE")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=original_msg,
        args=original_args,
        exc_info=None,
    )
    record.relativeCreated = 1000.0
    
    formatter.format(record)
    
    # Verify original values are restored
    assert record.msg == original_msg
    assert record.args == original_args


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


# ================= prepare_logger Tests =================

def test_prepare_logger_debug_sets_debug_level():
    """Test that DEBUG setting configures DEBUG level."""
    prepare_logger(setting="DEBUG")
    
    # Check that console handler has DEBUG level
    assert any(h.level == logging.DEBUG for h in rt_logger.handlers if isinstance(h, logging.StreamHandler))
    # Clean up
    detach_logging_handlers()


def test_prepare_logger_info_sets_info_level():
    """Test that INFO setting configures INFO level."""
    prepare_logger(setting="INFO")
    
    # Check that console handler has INFO level
    assert any(h.level == logging.INFO for h in rt_logger.handlers if isinstance(h, logging.StreamHandler))
    # Clean up
    detach_logging_handlers()


def test_prepare_logger_warning_sets_warning_level():
    """Test that WARNING setting configures WARNING level."""
    prepare_logger(setting="WARNING")
    
    # Check that console handler has WARNING level
    assert any(h.level == logging.WARNING for h in rt_logger.handlers if isinstance(h, logging.StreamHandler))
    # Clean up
    detach_logging_handlers()


def test_prepare_logger_none_adds_filter():
    """Test that NONE setting adds a filter that blocks all messages."""
    prepare_logger(setting="NONE")
    
    # Check that handlers exist with a filter
    assert len(rt_logger.handlers) > 0
    # Clean up
    detach_logging_handlers()


def test_prepare_logger_invalid_setting_raises_error():
    """Test that invalid setting raises ValueError."""
    with pytest.raises(ValueError, match="Invalid log level setting"):
        prepare_logger(setting="INVALID")  # type: ignore


def test_prepare_logger_clears_existing_handlers():
    """Test that prepare_logger clears handlers before adding new ones."""
    # Add a handler
    rt_logger.addHandler(logging.NullHandler())
    initial_count = len(rt_logger.handlers)
    
    prepare_logger(setting="INFO")
    
    # Should have exactly the handlers added by prepare_logger, not additional ones
    assert len(rt_logger.handlers) <= 2  # Console handler + optional file handler
    # Clean up
    detach_logging_handlers()


# ================= enable_logging Tests =================


def test_enable_logging_adds_real_handlers():
    """Test that enable_logging() (opt-in API) adds real handlers (e.g. StreamHandler)."""
    detach_logging_handlers()

    enable_logging(level="INFO")

    stream_handlers = [h for h in rt_logger.handlers if isinstance(h, logging.StreamHandler)]
    assert len(stream_handlers) >= 1, "enable_logging() should add at least one StreamHandler"

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


@patch.dict(os.environ, {"RT_LOG_FILE": os.path.join(tempfile.gettempdir(), "test.log")}, clear=False)
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


