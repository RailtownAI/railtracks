"""
Shared pytest fixtures for MCP Jupyter compatibility tests.

This file contains fixtures that are shared between multiple test files
in the rt_mcp test suite.
"""

import pytest
from unittest.mock import patch, MagicMock

from railtracks.rt_mcp.jupyter_compat import _patched


@pytest.fixture
def reset_patched_flag():
    """Reset the _patched flag to simulate a fresh import."""
    import railtracks.rt_mcp.jupyter_compat
    original_value = railtracks.rt_mcp.jupyter_compat._patched
    railtracks.rt_mcp.jupyter_compat._patched = False
    yield
    # Reset back to original state after test
    railtracks.rt_mcp.jupyter_compat._patched = original_value


@pytest.fixture
def jupyter_env_mock():
    """Mock is_jupyter to return True to simulate Jupyter environment."""
    with patch('railtracks.rt_mcp.jupyter_compat.is_jupyter', return_value=True):
        yield


@pytest.fixture
def normal_env_mock():
    """Mock is_jupyter to return False to simulate normal environment."""
    with patch('railtracks.rt_mcp.jupyter_compat.is_jupyter', return_value=False):
        yield


@pytest.fixture
def mock_server():
    """Mock MCPServer to avoid actually creating a server."""
    with patch('railtracks.rt_mcp.main.MCPServer') as mock_server:
        yield mock_server


@pytest.fixture
def mock_warnings():
    """Mock warnings.warn to check if it's called."""
    with patch('warnings.warn') as mock_warn:
        yield mock_warn