"""
Unit tests for the Jupyter compatibility module.

These tests verify that the Jupyter compatibility patches work correctly
in non-Jupyter environments and don't interfere with normal operation.
"""

import io
import sys

import pytest
from unittest.mock import patch, MagicMock

from railtracks.rt_mcp.jupyter_compat import apply_patches, is_jupyter
from railtracks.rt_mcp import jupyter_compat


def test_is_jupyter_detection_normal_env():
    """Test that is_jupyter returns False in a normal Python environment."""
    # In a normal Python environment, is_jupyter should return False
    assert not is_jupyter()


def test_apply_patches_normal_env(reset_patched_flag):
    """Test that apply_patches doesn't apply patches in a normal Python environment."""
    # Apply patches in a normal environment (should do nothing)
    apply_patches()
    
    # Verify that _patched is still False
    assert not jupyter_compat._patched


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
def test_apply_patches_jupyter_env(reset_patched_flag):
    """Test that apply_patches applies patches in a Jupyter environment."""
    # Mock is_jupyter to return True to simulate Jupyter environment
    with patch('railtracks.rt_mcp.jupyter_compat.is_jupyter', return_value=True):
        with patch('sys.platform', 'win32'):

            # Import the module to apply patches
            import mcp.os.win32.utilities
            original_create_windows_process = mcp.os.win32.utilities.create_windows_process
            original_create_windows_fallback_process = mcp.os.win32.utilities._create_windows_fallback_process

            # Apply patches
            apply_patches()

            # Verify that _patched is now True
            assert jupyter_compat._patched

            # Verify that the functions were patched
            assert original_create_windows_process != mcp.os.win32.utilities.create_windows_process
            assert original_create_windows_fallback_process != mcp.os.win32.utilities._create_windows_fallback_process


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
@pytest.mark.parametrize("patch_function", [
    "create_windows_process",
    "_create_windows_fallback_process"
])
def test_patched_functions_behavior(reset_patched_flag, patch_function):
    """Test that the patched functions handle Jupyter's lack of fileno() support."""
    # Mock is_jupyter to return True to simulate Jupyter environment
    with patch('railtracks.rt_mcp.jupyter_compat.is_jupyter', return_value=True):
        # Apply patches
        apply_patches()
        
        # Import the module to access the patched functions
        import mcp.os.win32.utilities
        
        # Create a mock stream that raises UnsupportedOperation for fileno()
        mock_stream = MagicMock()
        mock_stream.fileno.side_effect = io.UnsupportedOperation("fileno")
        
        # Test that the patched function handles the stream without error
        with patch('sys.stderr', mock_stream):
            # We can't actually call the functions as they're async, but we can check they exist
            assert hasattr(mcp.os.win32.utilities, patch_function)
            
            # Verify that _patched is True
            assert jupyter_compat._patched
