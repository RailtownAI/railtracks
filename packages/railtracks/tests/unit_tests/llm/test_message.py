import pytest
from typing import List
from railtracks.llm import UserMessage, SystemMessage, AssistantMessage, ToolMessage
from railtracks.llm.content import ToolResponse, ToolCall, Stream
from railtracks.llm.message import Attachment


# =================================== START Message Structure Tests ==================================
@pytest.mark.parametrize(
    "content, role, expected_str, expected_repr",
    [
        ("Hello", "user", "user: Hello", "user: Hello"),
        ("System message", "system", "system: System message", "system: System message"),
        ("Assistant response", "assistant", "assistant: Assistant response", "assistant: Assistant response"),
    ],
)
def test_message_str_and_repr(content, role, expected_str, expected_repr):
    if role == "user":
        message = UserMessage(content)
    elif role == "system":
        message = SystemMessage(content)
    elif role == "assistant":
        message = AssistantMessage(content)
    else:
        pytest.fail("Invalid role provided for test")

    assert str(message) == expected_str
    assert repr(message) == expected_repr


def test_system_message():
    message = SystemMessage("System message")
    assert message.content == "System message"
    assert message.role == "system"
    assert str(message) == "system: System message"
    assert repr(message) == "system: System message"


def test_assistant_message():
    message = AssistantMessage("Assistant response")
    assert message.content == "Assistant response"
    assert message.role == "assistant"
    assert str(message) == "assistant: Assistant response"
    assert repr(message) == "assistant: Assistant response"


def test_tool_message():
    tool_response = ToolResponse(name="tool1", result="result", identifier="123")
    message = ToolMessage(tool_response)
    assert message.content == tool_response
    assert message.role == "tool"
    assert str(message) == f"tool: {tool_response}"
    assert repr(message) == f"tool: {tool_response}"
    assert message.content.name == "tool1"
    assert message.content.result == "result"
    assert message.content.identifier == "123"


@pytest.mark.parametrize(
    "invalid_content, expected_exception",
    [
        (123, TypeError),
        (None, ValueError),
        (["list", "of", "strings"], TypeError),
    ],
)
def test_invalid_user_message_content(invalid_content, expected_exception):
    with pytest.raises(expected_exception):
        UserMessage(invalid_content)


@pytest.mark.parametrize(
    "invalid_content, expected_exception",
    [
        (123, TypeError),
        (None, TypeError),
        (["list", "of", "strings"], TypeError),
    ],
)
def test_invalid_system_message_content(invalid_content, expected_exception):
    with pytest.raises(expected_exception):
        SystemMessage(invalid_content)


def test_tool_message_invalid_content():
    with pytest.raises(TypeError):
        ToolMessage("Invalid content")  # ToolMessage expects ToolResponse, not str


def test_tool_message_invalid_content2():
    with pytest.raises(TypeError):
        ToolMessage(
            List[
                ToolCall(identifier="123", name="tool1", arguments={}),
                ToolCall(identifier="456", name="tool2", arguments={}),
            ]
        )  # ToolMessage expects ToolResponse, not List[ToolCall]

def test_tool_message_invalid_content3():
    with pytest.raises(TypeError):
        Stream(
            streamer="not a generator",
            final_message="Final message",
        ) # ToolMessage expects ToolResponse, not List[ToolResponse]

# =================================== END Message Structure Tests ==================================


# =================================== START Attachment Tests ==================================
class TestAttachment:
    @pytest.mark.parametrize(
        "extension,mime_type",
        [
            (".jpg", "jpeg"),
            (".jpeg", "jpeg"),
            (".png", "png"),
            (".gif", "gif"),
            (".webp", "webp"),
            (".PNG", "png"),
        ],
    )
    def test_local_file_formats(self, tmp_path, extension, mime_type):
        image_file = tmp_path / f"test{extension}"
        image_file.write_bytes(b"fake image data")

        attachment = Attachment(str(image_file))
        assert attachment.type == "local"
        assert attachment.modality == "image"
        assert attachment.encoding is not None
        assert f"data:image/{mime_type};base64," in attachment.encoding

    def test_unsupported_format(self, tmp_path):
        file = tmp_path / "test.txt"
        file.write_bytes(b"fake data")
        with pytest.raises(ValueError, match="Unsupported attachment format"):
            Attachment(str(file))

    def test_url(self):
        url = "https://example.com/image.png"
        attachment = Attachment(url)
        assert attachment.url == url
        assert attachment.type == "url"

    def test_data_uri(self):
        data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
        attachment = Attachment(data_uri)
        assert attachment.url == "..."
        assert attachment.encoding == data_uri
        assert attachment.type == "data_uri"

    def test_invalid_type(self):
        with pytest.raises(TypeError, match="url parameter must be a string"):
            Attachment(123)  # type: ignore


# =================================== END Attachment Tests ==================================


# =================================== START UserMessage Attachments Tests ==================================
class TestUserMessageAttachments:
    def test_single_attachment(self, tmp_path):
        image_file = tmp_path / "test.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        message = UserMessage("Check this", attachment=str(image_file))
        assert message.content == "Check this"
        assert message.attachment is not None
        assert len(message.attachment) == 1
        assert message.attachment[0].type == "local"

    def test_multiple_attachments(self, tmp_path):
        image1 = tmp_path / "test1.png"
        image1.write_bytes(b"\x89PNG\r\n\x1a\n")
        image2 = tmp_path / "test2.jpg"
        image2.write_bytes(b"\xff\xd8\xff")

        message = UserMessage("Check these", attachment=[str(image1), str(image2)])
        assert message.attachment is not None
        assert len(message.attachment) == 2
        assert all(att.type == "local" for att in message.attachment)

    def test_no_attachment(self):
        message = UserMessage("Just text")
        assert message.attachment is None

    @pytest.mark.parametrize(
        "attachment,expected_type",
        [
            ("https://example.com/image.png", "url"),
            ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA", "data_uri"),
        ],
    )
    def test_attachment_types(self, attachment, expected_type):
        message = UserMessage("Test", attachment=attachment)
        assert message.attachment is not None
        assert message.attachment[0].type == expected_type

    def test_mixed_attachments(self, tmp_path):
        local_file = tmp_path / "test.png"
        local_file.write_bytes(b"\x89PNG\r\n\x1a\n")
        attachments = [
            str(local_file),
            "https://example.com/image.jpg",
            "data:image/gif;base64,R0lGODlh",
        ]

        message = UserMessage("Mixed", attachment=attachments)
        assert message.attachment is not None
        assert len(message.attachment) == 3
        assert message.attachment[0].type == "local"
        assert message.attachment[1].type == "url"
        assert message.attachment[2].type == "data_uri"

# =================================== END UserMessage Attachments Tests ==================================


