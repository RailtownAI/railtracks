"""
Test MCP Error Handling
========================

Tests that verify proper error handling during MCP server connection setup,
including invalid commands, timeouts, and exception propagation from background threads.
"""

import threading
import time

import pytest
from railtracks.rt_mcp import MCPStdioParams
from railtracks.rt_mcp.main import MCPServer


class TestConnectionErrorHandling:
    """Test proper error handling during connection setup."""

    def test_invalid_command_raises_file_not_found(self):
        """Test that invalid commands properly raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            MCPServer(
                config=MCPStdioParams(
                    command="nonexistent_command_12345",
                    args=["test"]
                ),
                setup_timeout=5
            )
        
        # Verify error message is helpful
        assert "nonexistent_command_12345" in str(exc_info.value)
        assert "PATH" in str(exc_info.value) or "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_setup_exception_propagation(self, stdio_config, mock_client_session, patch_stdio_client, patch_ClientSession):
        """Test that exceptions during setup are properly propagated."""
        # Create a mock that raises an exception during connect
        mock_client_session.initialize.side_effect = ConnectionError("Failed to connect")
        
        with pytest.raises(RuntimeError) as exc_info:
            server = MCPServer(
                config=stdio_config,
                client_session=None,  # Force it to create new session
                setup_timeout=5
            )
        
        # Verify the error was propagated
        assert "Failed to connect" in str(exc_info.value) or exc_info.value.__cause__ is not None


class TestErrorContextAndMessages:
    """Test that error messages provide helpful context."""

    def test_file_not_found_has_helpful_message(self):
        """Test that FileNotFoundError includes helpful troubleshooting info."""
        with pytest.raises(FileNotFoundError) as exc_info:
            MCPServer(
                config=MCPStdioParams(
                    command="missing_mcp_server",
                    args=[]
                ),
                setup_timeout=5
            )
        
        error_msg = str(exc_info.value)
        # Should mention the command name
        assert "missing_mcp_server" in error_msg
        # Should provide helpful context
        assert any(hint in error_msg for hint in ["PATH", "installed", "not found"])


class TestThreadCleanup:
    """Test that threads are properly cleaned up after errors."""

    def test_thread_cleaned_up_after_error(self):
        """Test that background thread is cleaned up after connection error."""
        initial_thread_count = threading.active_count()
        
        try:
            MCPServer(
                config=MCPStdioParams(
                    command="nonexistent_command",
                    args=[]
                ),
                setup_timeout=5
            )
        except FileNotFoundError:
            pass  # Expected
        
        # Give threads time to clean up
        time.sleep(0.5)
        
        final_thread_count = threading.active_count()
        
        # Should not leak threads (allow small variance for system threads)
        assert final_thread_count <= initial_thread_count + 2


class TestSuccessfulConnection:
    """Sanity checks that valid connections still work."""

    @pytest.mark.asyncio
    async def test_valid_connection_succeeds(self, stdio_config, mock_client_session):
        """Test that valid connections work correctly."""
        server = MCPServer(
            config=stdio_config,
            client_session=mock_client_session,
            setup_timeout=30
        )
        
        # Should have tools
        assert server.tools is not None
        
        # Clean up
        server.close()

    def test_context_manager_cleanup_after_error(self, stdio_config, mock_client_session, patch_stdio_client, patch_ClientSession):
        """Test that context manager properly cleans up after errors."""
        mock_client_session.initialize.side_effect = ConnectionError("Test error")
        
        with pytest.raises(RuntimeError):
            with MCPServer(
                config=stdio_config,
                client_session=None,  # Force new session creation
                setup_timeout=5
            ) as server:
                pass
        
        # Context manager should handle cleanup even with error


class TestCloseMethod:
    """Test that close() method handles edge cases."""

    def test_close_without_init(self):
        """Test that close() can be called even if init failed early."""
        server = object.__new__(MCPServer)
        server._loop = None
        server._shutdown_event = None
        server._thread = None
        
        # Should not raise an error
        server.close()
