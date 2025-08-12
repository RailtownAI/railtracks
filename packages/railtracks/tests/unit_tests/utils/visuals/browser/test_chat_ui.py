import asyncio
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from railtracks.utils.visuals.browser.chat_ui import (
    ChatUI,
)


@pytest.fixture
def chat_ui():
    """Fixture providing a ChatUI instance for testing."""
    return ChatUI(port=8001, auto_open=False)  # Use different port to avoid conflicts


def test_chat_ui_initialization():
    """Test ChatUI initializes with correct default values."""
    chat_ui = ChatUI()
    assert chat_ui.port == 8000
    assert chat_ui.sse_queue is not None
    assert chat_ui.user_input_queue is not None
    assert chat_ui.app is not None
    assert chat_ui.server_thread is None

def test_chat_ui_initialization_custom_port():
    """Test ChatUI initializes with custom port."""
    custom_port = 9000
    chat_ui = ChatUI(port=custom_port)
    assert chat_ui.port == custom_port


@patch('railtracks.utils.visuals.browser.chat_ui.files')
def test_get_static_file_content_success(mock_files, chat_ui):
    """Test successful static file content retrieval."""
    mock_package = MagicMock()
    mock_file = Mock()
    mock_file.read_text.return_value = "test content"
    mock_package.__truediv__.return_value = mock_file
    mock_files.return_value = mock_package
    
    content = chat_ui._get_static_file_content("test.html")
    
    assert content == "test content"
    mock_files.assert_called_once_with('railtracks.utils.visuals.browser')
    mock_package.__truediv__.assert_called_once_with("test.html")
    mock_file.read_text.assert_called_once_with(encoding='utf-8')

@patch('railtracks.utils.visuals.browser.chat_ui.files')
def test_get_static_file_content_exception(mock_files, chat_ui):
    """Test static file content retrieval handles exceptions."""
    mock_files.side_effect = FileNotFoundError("File not found")
    
    with pytest.raises(Exception, match="Exception occurred loading static 'test.html' for Chat UI"):
        chat_ui._get_static_file_content("test.html")

@pytest.mark.asyncio
async def test_send_message(chat_ui):
    """Test sending assistant message to chat interface."""
    test_content = "Hello from assistant"
    
    await chat_ui.send_message(test_content)
    
    message = await chat_ui.sse_queue.get()
    assert message["type"] == "assistant_response"
    assert message["data"] == test_content
    assert "timestamp" in message

@pytest.mark.asyncio
async def test_update_tools(chat_ui):
    """Test sending tool invocation update to chat interface."""
    tool_name = "test_tool"
    tool_id = "tool_123"
    arguments = {"arg1": "value1"}
    result = "Success"
    
    await chat_ui.update_tools(tool_name, tool_id, arguments, result, True)
    
    message = await chat_ui.sse_queue.get()
    assert message["type"] == "tool_invoked"
    assert message["data"]["name"] == tool_name
    assert message["data"]["identifier"] == tool_id
    assert message["data"]["arguments"] == arguments
    assert message["data"]["result"] == result
    assert message["data"]["success"] is True

@pytest.mark.asyncio
async def test_update_tools_with_failure(chat_ui):
    """Test sending tool invocation update with failure status."""
    await chat_ui.update_tools("test_tool", "tool_123", {}, "Error occurred", False)
    
    message = await chat_ui.sse_queue.get()
    assert message["data"]["success"] is False
    assert message["data"]["result"] == "Error occurred"

@pytest.mark.asyncio
async def test_wait_for_user_input_success(chat_ui):
    """Test waiting for user input returns message."""
    test_message = {"message": "Hello", "timestamp": "2023-01-01T12:00:00"}
    
    # Put message in queue
    await chat_ui.user_input_queue.put(test_message)
    
    result = await chat_ui.wait_for_user_input()
    assert result == "Hello"

@pytest.mark.asyncio
async def test_wait_for_user_input_timeout():
    """Test waiting for user input with timeout returns None."""
    chat_ui = ChatUI()
    
    result = await chat_ui.wait_for_user_input(timeout=0.1)
    assert result is None

@pytest.mark.asyncio
async def test_wait_for_user_input_none_message(chat_ui):
    """Test waiting for user input with None message returns None."""
    await chat_ui.user_input_queue.put(None)
    
    result = await chat_ui.wait_for_user_input()
    assert result is None

@pytest.mark.asyncio
async def test_wait_for_user_input_no_timeout(chat_ui):
    """Test waiting for user input without timeout."""
    test_message = {"message": "Test message"}
    
    # Simulate delayed message
    async def delayed_put():
        await asyncio.sleep(0.1)
        await chat_ui.user_input_queue.put(test_message)
    
    # Start the delayed put task
    asyncio.create_task(delayed_put())
    
    result = await chat_ui.wait_for_user_input()
    assert result == "Test message"

@pytest.mark.asyncio
async def test_create_app_routes_exist(chat_ui):
    """Test that FastAPI app has all required routes."""
    app = chat_ui.app
    
    route_paths = [route.path for route in app.routes]
    
    assert "/" in route_paths
    assert "/send_message" in route_paths
    assert "/update_tools" in route_paths
    assert "/events" in route_paths
    assert "/chat.css" in route_paths
    assert "/chat.js" in route_paths


@patch('railtracks.utils.visuals.browser.chat_ui.uvicorn')
@patch('railtracks.utils.visuals.browser.chat_ui.threading')
def test_start_server_async_creates_thread(mock_threading, mock_uvicorn, chat_ui):
    """Test that start_server_async creates and starts a thread."""
    mock_thread = Mock()
    mock_threading.Thread.return_value = mock_thread
    
    url = chat_ui.start_server_async()
    
    assert url == f"http://{chat_ui.host}:{chat_ui.port}"
    mock_threading.Thread.assert_called_once()
    mock_thread.start.assert_called_once()
    assert chat_ui.server_thread == mock_thread

@patch('railtracks.utils.visuals.browser.chat_ui.uvicorn')
@patch('railtracks.utils.visuals.browser.chat_ui.threading')
def test_start_server_async_reuses_existing_thread(mock_threading, mock_uvicorn, chat_ui):
    """Test that start_server_async doesn't create new thread if one exists."""
    existing_thread = Mock()
    chat_ui.server_thread = existing_thread
    
    url = chat_ui.start_server_async()
    
    assert url == f"http://{chat_ui.host}:{chat_ui.port}"
    mock_threading.Thread.assert_not_called()
    assert chat_ui.server_thread == existing_thread

@patch('railtracks.utils.visuals.browser.chat_ui.uvicorn')
def test_run_server_calls_uvicorn(mock_uvicorn, chat_ui):
    """Test that run_server calls uvicorn with correct parameters."""
    chat_ui.run_server()
    
    mock_uvicorn.run.assert_called_once_with(
        chat_ui.app,
        host="127.0.0.1",
        port=chat_ui.port,
        log_level="warning"
    )

@pytest.mark.asyncio
async def test_message_flow_integration(chat_ui):
    """Test complete message flow from send to SSE queue."""
    # Test assistant message
    await chat_ui.send_message("Assistant response")
    sse_message = await chat_ui.sse_queue.get()
    
    assert sse_message["type"] == "assistant_response"
    assert sse_message["data"] == "Assistant response"
    
    # Test tool update
    await chat_ui.update_tools("tool", "id", {"arg": "val"}, "result")
    tool_message = await chat_ui.sse_queue.get()
    
    assert tool_message["type"] == "tool_invoked"
    assert tool_message["data"]["name"] == "tool"

@pytest.mark.asyncio
async def test_user_input_flow_integration(chat_ui):
    """Test complete user input flow from queue to retrieval."""
    user_data = {
        "message": "User question",
        "timestamp": datetime.now().isoformat()
    }
    
    # Simulate user input
    await chat_ui.user_input_queue.put(user_data)
    
    # Retrieve user input
    result = await chat_ui.wait_for_user_input()
    
    assert result == "User question"

@pytest.mark.asyncio
async def test_long_message_handling(chat_ui):
    """Test that ChatUI can handle very long messages (up to 200,000 characters)."""
    # Test maximum length message
    max_message = "B" * 200000  # Exactly 200,000 characters
    
    user_data = {
        "message": max_message,
        "timestamp": datetime.now().isoformat()
    }
    
    # Put maximum length message in queue
    await chat_ui.user_input_queue.put(user_data)
    
    # Retrieve the maximum length message
    result = await chat_ui.wait_for_user_input()
    
    assert result == max_message
    assert len(result) == 200000

@pytest.mark.asyncio
async def test_edge_case_messages(chat_ui):
    """Test edge cases: empty messages and short messages."""
    # Test empty message
    empty_message = ""
    user_data = {"message": empty_message, "timestamp": datetime.now().isoformat()}
    await chat_ui.user_input_queue.put(user_data)
    result = await chat_ui.wait_for_user_input()
    assert result == empty_message
    assert len(result) == 0
    
    # Test short message
    short_message = "Hello!"
    user_data = {"message": short_message, "timestamp": datetime.now().isoformat()}
    await chat_ui.user_input_queue.put(user_data)
    result = await chat_ui.wait_for_user_input()
    assert result == short_message
    assert len(result) == 6

@pytest.mark.asyncio
async def test_maximum_length_message_handling(chat_ui):
    """Test that ChatUI can handle the maximum allowed message length (200,000 characters)."""
    # Create a message at exactly the 200,000 character limit
    max_message = "B" * 200000  # Exactly 200,000 characters
    
    user_data = {
        "message": max_message,
        "timestamp": datetime.now().isoformat()
    }
    
    # Put maximum length message in queue
    await chat_ui.user_input_queue.put(user_data)
    
    # Retrieve the maximum length message
    result = await chat_ui.wait_for_user_input()
    
    assert result == max_message
    assert len(result) == 200000

@pytest.mark.asyncio
async def test_send_long_assistant_message(chat_ui):
    """Test sending very long assistant messages through the interface."""
    # Create a long assistant response
    long_response = "This is a very long assistant response. " * 5000  # ~200,000 characters
    long_response = long_response[:199999]  # Trim to just under 200k
    
    await chat_ui.send_message(long_response)
    
    message = await chat_ui.sse_queue.get()
    assert message["type"] == "assistant_response"
    assert message["data"] == long_response
    assert len(message["data"]) == 199999
    assert "timestamp" in message

@pytest.mark.asyncio
async def test_empty_message_handling(chat_ui):
    """Test that empty messages are handled correctly."""
    empty_message = ""
    
    user_data = {
        "message": empty_message,
        "timestamp": datetime.now().isoformat()
    }
    
    # Put empty message in queue
    await chat_ui.user_input_queue.put(user_data)
    
    # Retrieve the empty message
    result = await chat_ui.wait_for_user_input()
    
    assert result == empty_message
    assert len(result) == 0

@pytest.mark.asyncio
async def test_multiline_message_handling(chat_ui):
    """Test that multi-line messages with newlines are handled correctly."""
    multiline_message = "This is line 1\nThis is line 2\nThis is line 3"
    
    user_data = {
        "message": multiline_message,
        "timestamp": datetime.now().isoformat()
    }
    
    # Put multi-line message in queue
    await chat_ui.user_input_queue.put(user_data)
    
    # Retrieve the multi-line message
    result = await chat_ui.wait_for_user_input()
    
    assert result == multiline_message
    assert "\n" in result
    assert result.count("\n") == 2  # Two newline characters
    assert "line 1" in result and "line 2" in result and "line 3" in result

@pytest.mark.asyncio
async def test_send_multiline_assistant_message(chat_ui):
    """Test sending multi-line assistant messages through the interface."""
    multiline_response = "Here's a multi-line response:\n\n1. First point\n2. Second point\n3. Third point\n\nThat's all!"
    
    await chat_ui.send_message(multiline_response)
    
    message = await chat_ui.sse_queue.get()
    assert message["type"] == "assistant_response"
    assert message["data"] == multiline_response
    assert "\n" in message["data"]
    assert "First point" in message["data"]
    assert "timestamp" in message
