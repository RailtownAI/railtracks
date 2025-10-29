import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Adjust this import path to match your project structure
from railtracks.human_in_the_loop import (
    HILMessage,
    ChatUI,
)
from railtracks.human_in_the_loop.local_chat_ui import UIUserMessage, UserMessageAttachment
from railtracks.llm import ToolCall, ToolResponse


@pytest.fixture
def chat_ui():
    """Fixture to create a ChatUI instance for testing."""
    return ChatUI(port=8001, auto_open=False)


@pytest.fixture
def client(chat_ui):
    """Fixture to create a FastAPI TestClient."""
    return TestClient(chat_ui.app)


# ---- Initialization Tests ----


def test_chat_ui_initialization_defaults():
    """Test ChatUI initializes with default values."""
    ui = ChatUI()
    assert ui.port == 8000
    assert ui.host == "127.0.0.1"
    assert ui.auto_open is True
    assert isinstance(ui.sse_queue, asyncio.Queue)
    assert isinstance(ui.user_input_queue, asyncio.Queue)
    assert ui.is_connected is False


def test_chat_ui_initialization_custom():
    """Test ChatUI initializes with custom values."""
    ui = ChatUI(port=9999, host="0.0.0.0", auto_open=False)
    assert ui.port == 9999
    assert ui.host == "0.0.0.0"
    assert ui.auto_open is False


# ---- Static File Loading Tests ----


def test_get_static_file_content_success(chat_ui):
    """Test successful loading of a static file."""
    with patch("railtracks.human_in_the_loop.local_chat_ui.files") as mock_files:
        # Configure the mock to simulate the chained calls: files(...) / filename .read_text()
        mock_files.return_value.__truediv__.return_value.read_text.return_value = (
            "<html>Mock HTML</html>"
        )
        content = chat_ui._get_static_file_content("chat.html")
        assert content == "<html>Mock HTML</html>"


def test_get_static_file_content_file_not_found(chat_ui):
    """Test FileNotFoundError handling when a static file cannot be found."""
    with patch("railtracks.human_in_the_loop.local_chat_ui.files") as mock_files:
        # Simulate FileNotFoundError when accessing the file
        mock_files.return_value.__truediv__.return_value.read_text.side_effect = (
            FileNotFoundError("File not found")
        )
        with pytest.raises(
            FileNotFoundError,
            match=r"Static file 'nonexistent\.html' not found in package 'railtracks\.utils\.visuals\.browser'\.",
        ):
            chat_ui._get_static_file_content("nonexistent.html")


def test_get_static_file_content_generic_exception(chat_ui):
    """Test generic exception handling when loading a static file fails."""
    with patch("railtracks.human_in_the_loop.local_chat_ui.files") as mock_files:
        # Simulate a generic exception (not FileNotFoundError)
        mock_files.return_value.__truediv__.return_value.read_text.side_effect = (
            PermissionError("Permission denied")
        )
        with pytest.raises(
            Exception,
            match=r"Failed to load static file 'restricted\.html' for Chat UI: PermissionError: Permission denied",
        ):
            chat_ui._get_static_file_content("restricted.html")


# ---- FastAPI Endpoint Tests ----


def test_get_root_endpoint(client, chat_ui):
    """Test the root '/' endpoint serves HTML."""
    with patch.object(
        chat_ui,
        "_get_static_file_content",
        return_value="<h1>Chat</h1>",
    ) as mock_get_content:
        response = client.get("/")
        assert response.status_code == 200
        assert "<h1>Chat</h1>" in response.text
        mock_get_content.assert_called_once_with("chat.html")


def test_post_send_message_endpoint(client, chat_ui):
    """Test the '/send_message' endpoint."""
    test_message = "Hello from the user"
    response = client.post(
        "/send_message", json={"content": test_message, "timestamp": "12:34:56"}
    )
    assert response.status_code == 200
    queued_message = chat_ui.user_input_queue.get_nowait()
    assert isinstance(queued_message, HILMessage)
    assert queued_message.content == test_message


def test_post_update_tools_endpoint(client, chat_ui):
    """Test the '/update_tools' endpoint."""
    tool_data = {
        "name": "test_tool",
        "identifier": "tool_123",
        "arguments": {},
        "result": "Success!",
        "success": True,
    }
    response = client.post("/update_tools", json=tool_data)
    assert response.status_code == 200
    sse_message = chat_ui.sse_queue.get_nowait()
    assert sse_message["type"] == "tool_invoked"


@pytest.mark.asyncio
async def test_post_shutdown_endpoint(client, chat_ui):
    """Test the '/shutdown' endpoint."""
    chat_ui.is_connected = True
    with patch.object(chat_ui, "disconnect", new_callable=AsyncMock) as mock_disconnect:
        response = client.post("/shutdown")
        assert response.status_code == 200
        mock_disconnect.assert_awaited_once()


# ---- Connection Management Tests ----


@pytest.mark.asyncio
async def test_connect(chat_ui):
    """Test the connect method starts the server and sets state."""
    with (
        patch.object(chat_ui, "_run_server", new_callable=AsyncMock),
        patch("webbrowser.open"),
    ):
        await chat_ui.connect()
        assert chat_ui.is_connected is True
        chat_ui.server_task.cancel()
        try:
            await chat_ui.server_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_disconnect(chat_ui):
    """Test the disconnect method sets state correctly."""
    chat_ui.is_connected = True
    await chat_ui.disconnect()
    assert chat_ui.is_connected is False
    assert chat_ui.shutdown_event.is_set()


# ---- Message Handling Tests ----


@pytest.mark.asyncio
async def test_send_message_success(chat_ui):
    """Test sending a message successfully when connected."""
    chat_ui.is_connected = True
    await chat_ui.send_message(HILMessage(content="Hello AI"))
    sent_message = await chat_ui.sse_queue.get()
    assert sent_message["data"] == "Hello AI"


@pytest.mark.asyncio
async def test_receive_message_success(chat_ui):
    """Test receiving a message successfully."""
    chat_ui.is_connected = True
    expected_message = HILMessage(content="User input")
    await chat_ui.user_input_queue.put(expected_message)
    received_message = await chat_ui.receive_message(timeout=1)
    assert received_message == expected_message


# ---- Tool Update Tests ----


@pytest.mark.asyncio
async def test_update_tools_success(chat_ui):
    """Test updating tools successfully."""
    chat_ui.is_connected = True
    tool_call = ToolCall(
        name="get_weather", identifier="t1", arguments={"city": "Vancouver"}
    )
    tool_response = ToolResponse(
        name="get_weather", identifier="t1", result="Sunny, 20°C"
    )
    invocations = [(tool_call, tool_response)]

    result = await chat_ui.update_tools(invocations)
    assert result is True
    message = await chat_ui.sse_queue.get()
    assert message["data"]["name"] == "get_weather"
    assert message["data"]["success"] is True


@pytest.mark.asyncio
async def test_update_tools_failure(chat_ui):
    """Test updating tools with a failed tool response."""
    chat_ui.is_connected = True
    tool_call = ToolCall(
        name="get_weather", identifier="t2", arguments={"city": "Invalid"}
    )
    tool_response = ToolResponse(
        name="get_weather",
        identifier="t2",
        result="There was an error running the tool: Invalid city",
    )
    invocations = [(tool_call, tool_response)]

    result = await chat_ui.update_tools(invocations)
    assert result is True
    message = await chat_ui.sse_queue.get()
    assert message["data"]["success"] is False


@pytest.mark.asyncio
async def test_update_tools_queue_full(chat_ui):
    """Test update_tools when the SSE queue is full."""
    chat_ui.is_connected = True
    tool_call = ToolCall(name="test", identifier="t1", arguments={})
    tool_response = ToolResponse(name="test", identifier="t1", result="res")
    with patch.object(chat_ui.sse_queue, "put", side_effect=asyncio.QueueFull):
        result = await chat_ui.update_tools([(tool_call, tool_response)])
        assert result is False


# ---- Attachment Tests ----


def test_user_message_attachment_with_url():
    """Test UserMessageAttachment with URL type."""
    attachment = UserMessageAttachment(
        type="url",
        url="https://example.com/image.png",
        name="example_image"
    )
    assert attachment.type == "url"
    assert attachment.url == "https://example.com/image.png"
    assert attachment.data is None
    assert attachment.name == "example_image"


def test_user_message_attachment_with_data():
    """Test UserMessageAttachment with file data (base64)."""
    attachment = UserMessageAttachment(
        type="file",
        data="base64encodeddata==",
        name="document.pdf"
    )
    assert attachment.type == "file"
    assert attachment.data == "base64encodeddata=="
    assert attachment.url is None
    assert attachment.name == "document.pdf"


def test_user_message_attachment_validation_error():
    """Test UserMessageAttachment raises error when neither url nor data is provided."""
    with pytest.raises(ValueError, match="Either 'url' or 'data' must be provided."):
        UserMessageAttachment(type="file")


def test_ui_user_message_no_attachments():
    """Test UIUserMessage without attachments."""
    message = UIUserMessage(content="Hello AI")
    assert message.content == "Hello AI"
    assert message.attachments is None


def test_ui_user_message_with_file_attachment():
    """Test UIUserMessage with a file attachment."""
    attachment = UserMessageAttachment(
        type="file",
        data="base64data",
        name="test.txt"
    )
    message = UIUserMessage(
        content="Here's a file",
        attachments=[attachment]
    )
    assert message.content == "Here's a file"
    assert message.attachments is not None
    assert len(message.attachments) == 1
    assert message.attachments[0].type == "file"
    assert message.attachments[0].data == "base64data"


def test_ui_user_message_with_url_attachment():
    """Test UIUserMessage with a URL attachment."""
    attachment = UserMessageAttachment(
        type="url",
        url="https://example.com/doc.pdf"
    )
    message = UIUserMessage(
        content="Check this link",
        attachments=[attachment]
    )
    assert message.content == "Check this link"
    assert message.attachments is not None
    assert len(message.attachments) == 1
    assert message.attachments[0].type == "url"
    assert message.attachments[0].url == "https://example.com/doc.pdf"


def test_ui_user_message_with_multiple_attachments():
    """Test UIUserMessage with multiple attachments of different types."""
    file_attachment = UserMessageAttachment(
        type="file",
        data="filedata",
        name="file.txt"
    )
    url_attachment = UserMessageAttachment(
        type="url",
        url="https://example.com/image.jpg"
    )
    message = UIUserMessage(
        content="Multiple attachments",
        attachments=[file_attachment, url_attachment]
    )
    assert message.content == "Multiple attachments"
    assert message.attachments is not None
    assert len(message.attachments) == 2
    assert message.attachments[0].type == "file"
    assert message.attachments[1].type == "url"


def test_post_send_message_with_attachments(client, chat_ui):
    """Test the '/send_message' endpoint with attachments."""
    test_message = {
        "content": "Message with attachment",
        "timestamp": "12:34:56",
        "attachments": [
            {
                "type": "file",
                "data": "base64data==",
                "name": "document.pdf"
            }
        ]
    }
    response = client.post("/send_message", json=test_message)
    assert response.status_code == 200
    queued_message = chat_ui.user_input_queue.get_nowait()
    assert isinstance(queued_message, UIUserMessage)
    assert queued_message.content == "Message with attachment"
    assert queued_message.attachments is not None
    assert len(queued_message.attachments) == 1
    assert queued_message.attachments[0].type == "file"
    assert queued_message.attachments[0].data == "base64data=="
