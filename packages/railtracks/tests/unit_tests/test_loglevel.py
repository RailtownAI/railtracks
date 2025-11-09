"""
Tests for LogLevel enum and logging configuration
"""

import pytest
from unittest.mock import MagicMock, patch

import railtracks as rt
from railtracks import Session
from railtracks.utils.logging.config import LogLevel


# ================= START LogLevel Enum Tests ===============

def test_loglevel_enum_exists():
    """Test that LogLevel enum is exported and accessible"""
    assert hasattr(rt, "LogLevel")
    assert hasattr(rt.LogLevel, "DEBUG")
    assert hasattr(rt.LogLevel, "INFO")
    assert hasattr(rt.LogLevel, "WARNING")
    assert hasattr(rt.LogLevel, "ERROR")
    assert hasattr(rt.LogLevel, "CRITICAL")
    assert hasattr(rt.LogLevel, "NONE")
    assert hasattr(rt.LogLevel, "QUIET")


def test_loglevel_values():
    """Test that LogLevel enum has correct values"""
    assert rt.LogLevel.DEBUG.value == "DEBUG"
    assert rt.LogLevel.INFO.value == "INFO"
    assert rt.LogLevel.WARNING.value == "WARNING"
    assert rt.LogLevel.ERROR.value == "ERROR"
    assert rt.LogLevel.CRITICAL.value == "CRITICAL"
    assert rt.LogLevel.NONE.value == "NONE"
    assert rt.LogLevel.QUIET.value == "NONE"  # QUIET is alias for NONE


def test_loglevel_string_conversion():
    """Test that LogLevel converts to string correctly"""
    assert str(rt.LogLevel.DEBUG) == "DEBUG"
    assert str(rt.LogLevel.INFO) == "INFO"
    assert str(rt.LogLevel.NONE) == "NONE"
    assert str(rt.LogLevel.QUIET) == "NONE"  # QUIET converts to NONE


def test_quiet_is_alias_for_none():
    """Test that QUIET and NONE are equivalent"""
    assert rt.LogLevel.QUIET == rt.LogLevel.NONE
    assert rt.LogLevel.QUIET.value == rt.LogLevel.NONE.value


def test_loglevel_comparison():
    """Test that LogLevel enum values can be compared"""
    assert rt.LogLevel.DEBUG == rt.LogLevel.DEBUG
    assert rt.LogLevel.NONE == rt.LogLevel.QUIET
    assert rt.LogLevel.INFO != rt.LogLevel.DEBUG


def test_loglevel_enum_is_str_subclass():
    """Test that LogLevel enum inherits from str"""
    assert isinstance(rt.LogLevel.DEBUG, str)
    assert isinstance(rt.LogLevel.NONE, str)


# ================ END LogLevel Enum Tests ===============


# ================= START Session with LogLevel Tests ===============

@pytest.fixture
def mock_session_dependencies(monkeypatch):
    """Mock minimal Session dependencies - let ExecutorConfig work normally"""
    # Don't mock get_global_config - we want ExecutorConfig to work normally
    # Just mock the heavy dependencies we don't need for these tests
    m_RTPublisher = MagicMock()
    m_ExecutionInfo = MagicMock(create_new=MagicMock())
    m_Coordinator = MagicMock()
    m_RTState = MagicMock()
    m_register_globals = MagicMock()
    m_delete_globals = MagicMock()

    monkeypatch.setattr('railtracks._session.RTPublisher', m_RTPublisher)
    monkeypatch.setattr('railtracks._session.ExecutionInfo', m_ExecutionInfo)
    monkeypatch.setattr('railtracks._session.Coordinator', m_Coordinator)
    monkeypatch.setattr('railtracks._session.RTState', m_RTState)
    monkeypatch.setattr('railtracks._session.register_globals', m_register_globals)
    monkeypatch.setattr('railtracks._session.delete_globals', m_delete_globals)

    return {}


def test_session_accepts_loglevel_enum(mock_session_dependencies):
    """Test Session accepts LogLevel enum"""
    session = Session(logging_setting=rt.LogLevel.NONE)
    assert session.executor_config.logging_setting == "NONE"
    session._close()


def test_session_accepts_loglevel_quiet(mock_session_dependencies):
    """Test Session accepts LogLevel.QUIET (alias)"""
    session = Session(logging_setting=rt.LogLevel.QUIET)
    assert session.executor_config.logging_setting == "NONE"  # QUIET resolves to NONE
    session._close()


def test_session_accepts_string_backward_compat(mock_session_dependencies):
    """Test Session still accepts string values (backward compatibility)"""
    session = Session(logging_setting="NONE")
    assert session.executor_config.logging_setting == "NONE"
    session._close()


def test_session_accepts_string_quiet(mock_session_dependencies):
    """Test Session accepts string "QUIET" (alias for "NONE")"""
    session = Session(logging_setting="QUIET")
    assert session.executor_config.logging_setting == "QUIET"
    session._close()


def test_all_loglevel_enums_work_with_session(mock_session_dependencies):
    """Test all LogLevel enum values work with Session"""
    for level in [
        rt.LogLevel.DEBUG,
        rt.LogLevel.INFO,
        rt.LogLevel.WARNING,
        rt.LogLevel.ERROR,
        rt.LogLevel.CRITICAL,
        rt.LogLevel.NONE,
        rt.LogLevel.QUIET,
    ]:
        session = Session(logging_setting=level)
        # Should not raise an error
        session._close()


def test_all_loglevel_strings_work_with_session(mock_session_dependencies):
    """Test all valid string values work with Session (backward compatibility)"""
    for level_str in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE", "QUIET"]:
        session = Session(logging_setting=level_str)
        # Should not raise an error
        session._close()


def test_invalid_logging_level_raises_error(mock_session_dependencies):
    """Test that invalid logging levels raise helpful errors"""
    with pytest.raises(ValueError) as exc_info:
        Session(logging_setting="INVALID_LEVEL")

    error_msg = str(exc_info.value)
    assert "logging_setting must be one of" in error_msg
    assert "INVALID_LEVEL" in error_msg


def test_invalid_logging_levels_variants(mock_session_dependencies):
    """Test various invalid logging level strings"""
    invalid_levels = ["SILENT", "MUTE", "OFF", "VERBOSE", "verbose", "quiet"]
    
    for invalid_level in invalid_levels:
        with pytest.raises(ValueError) as exc_info:
            Session(logging_setting=invalid_level)
        
        error_msg = str(exc_info.value)
        assert "logging_setting must be one of" in error_msg


# ================ END Session with LogLevel Tests ===============


# ================= START LogLevel in set_config Tests ===============

def test_loglevel_works_with_set_config(mock_session_dependencies):
    """Test that LogLevel works with set_config"""
    # Should not raise an error
    rt.set_config(logging_setting=rt.LogLevel.NONE)
    
    # Reset to default
    rt.set_config(logging_setting=rt.LogLevel.INFO)


def test_loglevel_string_works_with_set_config(mock_session_dependencies):
    """Test that string values still work with set_config"""
    rt.set_config(logging_setting="NONE")
    rt.set_config(logging_setting="INFO")  # Reset


# ================ END LogLevel in set_config Tests ===============


# ================= START Documentation Tests ===============

def test_loglevel_enum_documented_in_session():
    """Test that LogLevel is mentioned in Session docstring"""
    assert "LogLevel" in Session.__doc__
    assert "rt.LogLevel.NONE" in Session.__doc__
    assert "rt.LogLevel.QUIET" in Session.__doc__


def test_loglevel_enum_has_docstring():
    """Test that LogLevel enum has comprehensive docstring"""
    assert LogLevel.__doc__ is not None
    assert "IDE autocomplete" in LogLevel.__doc__
    assert "DEBUG" in LogLevel.__doc__
    assert "NONE" in LogLevel.__doc__
    assert "QUIET" in LogLevel.__doc__


def test_loglevel_enum_attributes_documented():
    """Test that LogLevel enum attributes are documented"""
    docstring = LogLevel.__doc__
    # Check that all levels are mentioned
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE", "QUIET"]:
        assert level in docstring


# ================ END Documentation Tests ===============


# ================= START Integration Tests ===============

def test_loglevel_enum_and_string_produce_same_config(mock_session_dependencies):
    """Test that using LogLevel enum vs string produces identical configuration"""
    session1 = Session(logging_setting=rt.LogLevel.NONE)
    session2 = Session(logging_setting="NONE")
    
    assert session1.executor_config.logging_setting == session2.executor_config.logging_setting
    
    session1._close()
    session2._close()


def test_loglevel_quiet_and_none_produce_same_config(mock_session_dependencies):
    """Test that QUIET and NONE produce identical configuration"""
    session1 = Session(logging_setting=rt.LogLevel.QUIET)
    session2 = Session(logging_setting=rt.LogLevel.NONE)
    session3 = Session(logging_setting="NONE")
    
    assert session1.executor_config.logging_setting == "NONE"
    assert session2.executor_config.logging_setting == "NONE"
    assert session3.executor_config.logging_setting == "NONE"
    
    session1._close()
    session2._close()
    session3._close()


def test_string_quiet_works_as_alias(mock_session_dependencies):
    """Test that string "QUIET" works as an alias for "NONE" """
    session_quiet_enum = Session(logging_setting=rt.LogLevel.QUIET)
    session_quiet_string = Session(logging_setting="QUIET")
    session_none_string = Session(logging_setting="NONE")
    
    # All should be valid and use QUIET or NONE (both map to same log level)
    # Note: The enum converts to "NONE" but the string stays as "QUIET"
    assert session_quiet_enum.executor_config.logging_setting == "NONE"  # Enum QUIET -> "NONE"
    assert session_quiet_string.executor_config.logging_setting == "QUIET"  # String "QUIET" -> "QUIET"
    assert session_none_string.executor_config.logging_setting == "NONE"  # String "NONE" -> "NONE"
    
    session_quiet_enum._close()
    session_quiet_string._close()
    session_none_string._close()


# ================ END Integration Tests ===============


# ================= START Edge Cases ===============

def test_loglevel_none_vs_python_none(mock_session_dependencies):
    """Test that LogLevel.NONE is different from Python's None"""
    assert rt.LogLevel.NONE is not None
    assert rt.LogLevel.NONE != None
    assert str(rt.LogLevel.NONE) == "NONE"


def test_session_with_none_logging_uses_global_config(mock_session_dependencies):
    """Test that passing None for logging_setting uses global config, not hardcoded default"""
    # When None is passed, it should use whatever is in global config
    session1 = Session(logging_setting=None)
    session2 = Session()  # No logging_setting specified
    
    # Both should use the same value from global config
    assert session1.executor_config.logging_setting == session2.executor_config.logging_setting
    
    # Get the current global default (usually "INFO" but could be configured differently)
    global_default = session1.executor_config.logging_setting
    
    # Verify it's different from explicitly setting LogLevel.NONE/QUIET
    session3 = Session(logging_setting=rt.LogLevel.NONE)
    assert session3.executor_config.logging_setting == "NONE"
    
    # The global config default should be different from NONE (unless explicitly set)
    # This ensures Python None != LogLevel.NONE
    if global_default != "NONE":
        assert session3.executor_config.logging_setting != session1.executor_config.logging_setting
    
    session1._close()
    session2._close()
    session3._close()


# ================ END Edge Cases ===============


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
