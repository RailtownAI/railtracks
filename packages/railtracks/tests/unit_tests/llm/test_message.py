from copy import deepcopy
from typing import List

import pytest
from railtracks.llm import AssistantMessage, SystemMessage, ToolMessage, UserMessage
from railtracks.llm.content import Stream, ToolCall, ToolCalls, ToolResponse
from railtracks.llm.message import Attachment, Message, Role


# =================================== START Message Structure Tests ==================================
@pytest.mark.parametrize(
    "content, role, expected_str, expected_repr",
    [
        ("Hello", "user", "user: Hello", "user: Hello"),
        (
            "System message",
            "system",
            "system: System message",
            "system: System message",
        ),
        (
            "Assistant response",
            "assistant",
            "assistant: Assistant response",
            "assistant: Assistant response",
        ),
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


def test_assistant_message_reasoning_defaults_none_and_absent_from_encode():
    message = AssistantMessage("Assistant response")
    assert message.reasoning_content is None
    assert message.thinking_blocks is None
    encoded = message.encode()
    assert "reasoning_content" not in encoded
    assert "thinking_blocks" not in encoded


def test_assistant_message_encode_surfaces_reasoning():
    blocks = [{"type": "thinking", "thinking": "2 + 2", "signature": "sig"}]
    message = AssistantMessage("4")
    message.reasoning_content = "2 + 2 is 4"
    message.thinking_blocks = blocks

    encoded = message.encode()

    assert encoded["reasoning_content"] == "2 + 2 is 4"
    assert encoded["thinking_blocks"] == blocks


def test_copy_metadata_from_carries_all_metadata():
    blocks = [{"type": "thinking", "thinking": "2 + 2", "signature": "sig"}]
    source = AssistantMessage("4")
    source.raw_litellm_message = {"raw": "msg"}
    source.reasoning_content = "2 + 2 is 4"
    source.thinking_blocks = blocks

    rebuilt = AssistantMessage("4").copy_metadata_from(source)

    assert rebuilt.raw_litellm_message == {"raw": "msg"}
    assert rebuilt.reasoning_content == "2 + 2 is 4"
    assert rebuilt.thinking_blocks == blocks


def test_copy_metadata_from_plain_message_is_noop():
    # A plain Message source (no assistant metadata) leaves the defaults untouched.
    rebuilt = AssistantMessage("4").copy_metadata_from(
        Message(role=Role.assistant, content="4")
    )
    assert rebuilt.raw_litellm_message is None
    assert rebuilt.reasoning_content is None
    assert rebuilt.thinking_blocks is None


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
        )  # ToolMessage expects ToolResponse, not List[ToolResponse]


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
            (".avif", "avif"),
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
        file = tmp_path / "test.xyz"
        file.write_bytes(b"fake data")
        with pytest.raises(ValueError, match="Unsupported attachment format"):
            Attachment(str(file))

    def test_local_text_file_is_a_file_attachment(self, tmp_path):
        file = tmp_path / "notes.txt"
        file.write_bytes(b"BMW sales notes")  # starts like a BMP signature

        attachment = Attachment(str(file))
        assert attachment.modality == "file"
        assert attachment.mime_type == "text/plain"

    def test_local_pdf(self, tmp_path):
        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%fake pdf body\n%%EOF")

        attachment = Attachment(str(pdf_file))
        assert attachment.type == "local"
        assert attachment.modality == "document"
        assert attachment.mime_type == "application/pdf"
        assert attachment.filename == "doc.pdf"
        assert attachment.encoding is not None
        assert attachment.encoding.startswith("data:application/pdf;base64,")

    def test_base64_pdf(self):
        import base64 as _b64

        pdf_bytes = b"%PDF-1.4\n%fake pdf body\n%%EOF"
        b64 = _b64.b64encode(pdf_bytes).decode("utf-8")

        attachment = Attachment(b64)
        assert attachment.type == "data_uri"
        assert attachment.modality == "document"
        assert attachment.mime_type == "application/pdf"
        assert attachment.filename is None
        assert attachment.encoding is not None
        assert attachment.encoding.startswith("data:application/pdf;base64,")

    def test_data_uri_pdf(self):
        import base64 as _b64

        pdf_bytes = b"%PDF-1.4\n%fake pdf body\n%%EOF"
        b64 = _b64.b64encode(pdf_bytes).decode("utf-8")
        data_uri = f"data:application/pdf;base64,{b64}"

        attachment = Attachment(data_uri)
        assert attachment.type == "data_uri"
        assert attachment.modality == "document"
        assert attachment.mime_type == "application/pdf"
        assert attachment.filename is None
        assert attachment.encoding == data_uri

    def test_data_uri_pdf_mixed_case_mime(self):
        """Header validation is case-insensitive, so modality classification must be too."""
        import base64 as _b64

        pdf_bytes = b"%PDF-1.4\n%fake pdf body\n%%EOF"
        b64 = _b64.b64encode(pdf_bytes).decode("utf-8")
        data_uri = f"data:Application/PDF;base64,{b64}"

        attachment = Attachment(data_uri)
        assert attachment.type == "data_uri"
        assert attachment.modality == "document"
        assert attachment.mime_type == "application/pdf"

    def test_url(self):
        url = "https://example.com/image.png"
        attachment = Attachment(url)
        assert attachment.url == url
        assert attachment.type == "url"
        assert attachment.modality == "image"
        assert attachment.mime_type == "image/png"
        assert attachment.filename == "image.png"
        # Image URLs are passed to the provider as-is; no fetch at construction.
        assert attachment.encoding is None

    def test_url_avif(self):
        attachment = Attachment("https://example.com/photo.avif")
        assert attachment.type == "url"
        assert attachment.modality == "image"
        assert attachment.mime_type == "image/avif"
        assert attachment.encoding is None

    def test_url_with_query_string(self):
        url = "https://example.com/photo.png?token=abc&x=1"
        attachment = Attachment(url)
        assert attachment.type == "url"
        assert attachment.modality == "image"
        assert attachment.mime_type == "image/png"
        assert attachment.filename == "photo.png"

    def test_attachment_limits_thread_to_probe_and_encode(self, monkeypatch):
        """attachment_timeout must reach the HEAD probe and the download, and
        attachment_max_mb must reach the download."""
        from railtracks.llm import message as message_module

        pdf_bytes = b"%PDF-1.4\n%remote pdf body\n%%EOF"
        seen = {}

        class _FakeResp:
            headers = {
                "Content-Type": "application/pdf",
                "Content-Disposition": 'inline; filename="paper.pdf"',
            }

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            seen["probe_timeout"] = timeout
            return _FakeResp()

        def fake_load_bytes(path, *, timeout=10.0, max_mb=32.0):
            seen["encode_timeout"] = timeout
            seen["encode_max_mb"] = max_mb
            return pdf_bytes

        monkeypatch.setattr(message_module.urllib_request, "urlopen", fake_urlopen)
        monkeypatch.setattr(message_module, "load_bytes", fake_load_bytes)

        UserMessage(
            content="Summarize.",
            attachment="https://example.com/no-ext",
            trust_urls=True,
            attachment_timeout=42.0,
            attachment_max_mb=5.0,
        )
        assert seen["probe_timeout"] == 42.0
        assert seen["encode_timeout"] == 42.0
        assert seen["encode_max_mb"] == 5.0

    @pytest.mark.parametrize("max_mb", [0, -1, float("inf"), float("nan")])
    def test_attachment_max_mb_must_be_positive_and_finite(self, max_mb):
        with pytest.raises(ValueError, match="attachment_max_mb"):
            Attachment(
                "https://example.com/doc.pdf", trust_urls=True, attachment_max_mb=max_mb
            )

    def test_url_pdf_is_fetched_and_encoded(self, monkeypatch):
        from railtracks.llm import message as message_module

        pdf_bytes = b"%PDF-1.4\n%remote pdf body\n%%EOF"

        def fake_load_bytes(path, *, timeout=10.0, max_mb=32.0):
            assert path == "https://example.com/docs/report.pdf?sig=xyz"
            return pdf_bytes

        monkeypatch.setattr(message_module, "load_bytes", fake_load_bytes)

        attachment = Attachment(
            "https://example.com/docs/report.pdf?sig=xyz", trust_urls=True
        )
        assert attachment.type == "url"
        assert attachment.modality == "document"
        assert attachment.mime_type == "application/pdf"
        assert attachment.filename == "report.pdf"
        assert attachment.encoding is not None
        assert attachment.encoding.startswith("data:application/pdf;base64,")

    def test_pdf_url_without_trust_urls_raises(self, monkeypatch):
        """
        A .pdf URL without trust_urls=True must refuse to fetch — that's the
        whole point of the gate. load_bytes() must not be called.
        """
        from railtracks.llm import message as message_module

        def boom_load_bytes(path, *, timeout=10.0, max_mb=32.0):
            raise AssertionError(f"load_bytes() must not be called for {path!r}")

        monkeypatch.setattr(message_module, "load_bytes", boom_load_bytes)

        with pytest.raises(ValueError, match="trust_urls=True"):
            Attachment("https://example.com/docs/report.pdf")

    def test_url_without_extension_probes_content_type(self, monkeypatch):
        """
        Real-world case: https://arxiv.org/pdf/1706.03762 has no .pdf extension
        but serves application/pdf. With trust_urls=True we HEAD-probe the URL
        and use Content-Type + Content-Disposition to classify it as a document.
        """
        from railtracks.llm import message as message_module

        pdf_bytes = b"%PDF-1.4\n%remote pdf body\n%%EOF"

        class _FakeResp:
            headers = {
                "Content-Type": "application/pdf",
                "Content-Disposition": 'inline; filename="1706.03762v7.pdf"',
            }

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            assert req.get_method() == "HEAD"
            return _FakeResp()

        def fake_load_bytes(path, *, timeout=10.0, max_mb=32.0):
            return pdf_bytes

        monkeypatch.setattr(message_module.urllib_request, "urlopen", fake_urlopen)
        monkeypatch.setattr(message_module, "load_bytes", fake_load_bytes)

        attachment = Attachment("https://arxiv.org/pdf/1706.03762", trust_urls=True)
        assert attachment.modality == "document"
        assert attachment.mime_type == "application/pdf"
        assert attachment.filename == "1706.03762v7.pdf"
        assert attachment.encoding is not None
        assert attachment.encoding.startswith("data:application/pdf;base64,")

    def test_url_without_extension_skips_probe_when_untrusted(self, monkeypatch):
        """
        Without trust_urls, no HEAD probe is issued — even for a URL that would
        otherwise look like a PDF. Falls back to image so the provider can try
        the URL as-is.
        """
        from railtracks.llm import message as message_module

        def boom_urlopen(req, timeout=None):
            raise AssertionError("HEAD probe must not be issued when trust_urls=False")

        monkeypatch.setattr(message_module.urllib_request, "urlopen", boom_urlopen)

        attachment = Attachment("https://arxiv.org/pdf/1706.03762")
        assert attachment.modality == "image"
        assert attachment.mime_type is None
        assert attachment.encoding is None

    def test_url_probe_failure_defaults_to_image(self, monkeypatch):
        """If HEAD fails when trust_urls=True, fall back to image so the provider can try the URL."""
        from urllib.error import URLError

        from railtracks.llm import message as message_module

        def fake_urlopen(req, timeout=None):
            raise URLError("nope")

        monkeypatch.setattr(message_module.urllib_request, "urlopen", fake_urlopen)

        attachment = Attachment(
            "https://example.com/something-no-extension", trust_urls=True
        )
        assert attachment.modality == "image"
        assert attachment.mime_type is None
        assert attachment.encoding is None

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/report.docx",
            "https://example.com/sheet.xlsx",
            "https://example.com/notes.txt",
            "https://example.com/NOTES.TXT",
            "https://example.com/page.html?token=abc",
        ],
    )
    def test_url_with_document_extension_raises(self, url):
        """A URL whose extension names a text or Office type must not be sent as an image."""
        with pytest.raises(ValueError, match="Unsupported attachment format"):
            Attachment(url)

    @pytest.mark.parametrize(
        "url,modality,mime_type",
        [
            ("https://example.com/call.mp3", "audio", "audio/mpeg"),
            ("https://example.com/CALL.MP3", "audio", "audio/mpeg"),
            ("https://example.com/call.mp3?token=abc", "audio", "audio/mpeg"),
            ("https://example.com/voice.wav", "audio", "audio/wav"),
            ("https://example.com/memo.m4a", "audio", "audio/mp4"),
            ("https://example.com/clip.mp4", "video", "video/mp4"),
        ],
    )
    def test_url_with_audio_or_video_extension(self, url, modality, mime_type):
        attachment = Attachment(url)
        assert attachment.modality == modality
        assert attachment.mime_type == mime_type
        assert attachment.encoding is None

    @pytest.mark.parametrize(
        "extension",
        [".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"]
        + [".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm", ".wmv"],
    )
    def test_audio_and_video_urls_are_never_sent_as_images(self, extension):
        """Every Python version must type these, or they fall back to `image_url`."""
        attachment = Attachment(f"https://example.com/media{extension}")
        assert attachment.modality in ("audio", "video")

    @pytest.mark.parametrize(
        "url",
        [
            "https://cdn.example.com/abc123",
            "https://example.com/thumb.php?id=3",
            "https://example.com/GetImage.ashx?id=1",
            "https://example.com/img.pl?id=3",
            "https://example.com/photo.svg",
        ],
    )
    def test_url_without_non_image_extension_still_passes_as_image(self, url):
        attachment = Attachment(url)
        assert attachment.modality == "image"
        assert attachment.encoding is None

    def test_trusted_non_image_extension_accepted_when_probe_reports_image(
        self, monkeypatch
    ):
        """A video path rendered as a thumbnail is classified by its Content-Type."""
        from railtracks.llm import message as message_module

        monkeypatch.setattr(
            message_module,
            "_probe_url_metadata",
            lambda url, *, timeout: ("image/jpeg", None),
        )

        attachment = Attachment(
            "https://example.com/clip.mp4?video-thumbnail=auto", trust_urls=True
        )
        assert attachment.modality == "image"
        assert attachment.mime_type == "image/jpeg"

    @pytest.mark.parametrize("probed_ct", ["text/html", None])
    def test_trusted_audio_extension_kept_when_probe_reports_no_media(
        self, monkeypatch, probed_ct
    ):
        from railtracks.llm import message as message_module

        monkeypatch.setattr(
            message_module,
            "_probe_url_metadata",
            lambda url, *, timeout: (probed_ct, None),
        )

        attachment = Attachment("https://example.com/call.mp3", trust_urls=True)
        assert attachment.modality == "audio"
        assert attachment.mime_type == "audio/mpeg"

    def test_user_message_rejects_document_url(self):
        with pytest.raises(ValueError, match="Unsupported attachment format"):
            UserMessage("Summarize this", attachment="https://example.com/memo.docx")

    def test_user_message_threads_trust_urls(self, monkeypatch):
        """UserMessage(trust_urls=True) must propagate to every Attachment it builds."""
        from railtracks.llm import message as message_module

        pdf_bytes = b"%PDF-1.4\n%remote pdf body\n%%EOF"

        def fake_load_bytes(path, *, timeout=10.0, max_mb=32.0):
            return pdf_bytes

        monkeypatch.setattr(message_module, "load_bytes", fake_load_bytes)

        # Without trust_urls the PDF URL is rejected.
        with pytest.raises(ValueError, match="trust_urls=True"):
            UserMessage(
                content="Summarize.",
                attachment="https://example.com/report.pdf",
            )

        # With trust_urls=True the same call succeeds and fetches in-process.
        msg = UserMessage(
            content="Summarize.",
            attachment=["https://example.com/report.pdf"],
            trust_urls=True,
        )
        assert msg.attachment[0].modality == "document"
        assert msg.attachment[0].encoding.startswith("data:application/pdf;base64,")

    def test_data_uri(self):
        data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
        attachment = Attachment(data_uri)
        assert attachment.url == "..."
        assert attachment.encoding == data_uri
        assert attachment.type == "data_uri"

    def test_invalid_type(self):
        with pytest.raises(TypeError, match="url parameter must be a string"):
            Attachment(123)  # type: ignore


_PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(32))
_WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + bytes(16)
_MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00"


class TestAttachmentContent:
    @pytest.mark.parametrize(
        "data,kwargs,mime_type,modality",
        [
            (_PNG, {}, "image/png", "image"),
            (_WAV, {}, "audio/wav", "audio"),
            (_MP4, {}, "video/mp4", "video"),
            (b"%PDF-1.7\n", {}, "application/pdf", "document"),
            (b"col,val\n", {"filename": "data.csv"}, "text/csv", "file"),
            (b"anything", {"mime_type": "Audio/OGG"}, "audio/ogg", "audio"),
            (_PNG, {"mime_type": "image/jpeg"}, "image/jpeg", "image"),
        ],
        ids=["magic", "wav", "mp4", "pdf", "filename", "explicit", "explicit_wins"],
    )
    def test_from_bytes_detects_type(self, data, kwargs, mime_type, modality):
        attachment = Attachment.from_bytes(data, **kwargs)
        assert attachment.type == "data_uri"
        assert attachment.url == "..."
        assert attachment.mime_type == mime_type
        assert attachment.modality == modality
        assert attachment.data == data
        assert attachment.size == len(data)
        assert attachment.filename == kwargs.get("filename")

    def test_from_bytes_rejects_unknown_type(self):
        with pytest.raises(ValueError, match="pass mime_type"):
            Attachment.from_bytes(b"no magic here")

    def test_from_bytes_rejects_empty_data(self):
        with pytest.raises(ValueError, match="empty"):
            Attachment.from_bytes(b"", mime_type="image/png")

    def test_from_bytes_rejects_non_bytes(self):
        with pytest.raises(TypeError, match="must be bytes"):
            Attachment.from_bytes("iVBORw0KGgo=")  # type: ignore[arg-type]

    def test_sha256_is_stable_across_sources(self, tmp_path):
        import base64 as _b64
        import hashlib

        image_file = tmp_path / "chart.png"
        image_file.write_bytes(_PNG)
        b64 = _b64.b64encode(_PNG).decode("utf-8")

        attachments = [
            Attachment(str(image_file)),
            Attachment.from_bytes(_PNG),
            Attachment(f"data:image/png;base64,{b64}"),
            Attachment(b64),
            Attachment(b64.rstrip("=")),
        ]

        assert {a.sha256 for a in attachments} == {hashlib.sha256(_PNG).hexdigest()}
        assert all(a.size == len(_PNG) for a in attachments)
        assert all(a == attachments[0] for a in attachments)
        assert len(set(attachments)) == 1

    def test_local_magic_bytes_win_over_extension(self, tmp_path):
        mislabeled = tmp_path / "photo.png"
        mislabeled.write_bytes(b"\xff\xd8\xff\xe0" + bytes(16))
        assert Attachment(str(mislabeled)).mime_type == "image/jpeg"

    def test_local_file_is_read_once(self, tmp_path):
        image_file = tmp_path / "chart.png"
        image_file.write_bytes(_PNG)
        attachment = Attachment(str(image_file))
        image_file.write_bytes(b"\xff\xd8\xff" + bytes(8))

        assert attachment.data == _PNG
        assert attachment.encoding == Attachment.from_bytes(_PNG).encoding

    def test_local_empty_file_raises(self, tmp_path):
        empty = tmp_path / "empty.png"
        empty.write_bytes(b"")
        with pytest.raises(ValueError, match="empty"):
            Attachment(str(empty))

    def test_data_uri_with_invalid_payload_raises(self):
        with pytest.raises(ValueError, match="not valid base64"):
            Attachment("data:image/png;base64,***")

    def test_url_attachment_has_no_bytes(self):
        attachment = Attachment("https://example.com/image.png")
        assert attachment.data is None
        assert attachment.size is None
        assert attachment.sha256 is None

    def test_equality(self):
        jpeg = b"\xff\xd8\xff\xe0" + bytes(16)
        assert Attachment.from_bytes(_PNG) != Attachment.from_bytes(jpeg)
        assert Attachment.from_bytes(_PNG) != Attachment.from_bytes(
            _PNG, mime_type="image/x-png"
        )
        assert Attachment("https://example.com/a.png") == Attachment(
            "https://example.com/a.png"
        )
        assert Attachment("https://example.com/a.png") != Attachment(
            "https://example.com/b.png"
        )
        assert Attachment.from_bytes(_PNG) != _PNG

    def test_deepcopy_keeps_identity_and_shares_bytes(self):
        attachment = Attachment.from_bytes(_PNG, filename="chart.png")
        copied = deepcopy(attachment)

        assert copied == attachment
        assert copied.sha256 == attachment.sha256
        assert copied.data is attachment.data

    def test_repr_has_no_payload(self):
        attachment = Attachment.from_bytes(_PNG, filename="chart.png")
        assert repr(attachment) == (
            f"Attachment(type='data_uri', mime_type='image/png', "
            f"filename='chart.png', size={len(_PNG)})"
        )
        assert repr(Attachment("https://example.com/a.png")) == (
            "Attachment(type='url', mime_type='image/png', "
            "url='https://example.com/a.png', filename='a.png')"
        )

    def test_from_url_with_explicit_type_skips_probe(self, monkeypatch):
        from railtracks.llm import message as message_module

        def boom_probe(url, *, timeout):
            raise AssertionError("an explicit mime_type must skip the HEAD probe")

        monkeypatch.setattr(message_module, "_probe_url_metadata", boom_probe)

        attachment = Attachment.from_url(
            "https://cdn.example.com/abc123",
            mime_type="audio/mpeg",
            filename="call.mp3",
            trust_urls=True,
        )
        assert attachment.type == "url"
        assert attachment.modality == "audio"
        assert attachment.filename == "call.mp3"
        assert attachment.encoding is None

    def test_from_url_pdf_still_requires_trust_urls(self):
        with pytest.raises(ValueError, match="trust_urls=True"):
            Attachment.from_url(
                "https://cdn.example.com/abc123", mime_type="application/pdf"
            )

    def test_from_url_explicit_type_allows_document_extension(self):
        attachment = Attachment.from_url(
            "https://example.com/notes.txt", mime_type="text/plain"
        )
        assert attachment.modality == "file"

    def test_from_url_rejects_non_url(self, tmp_path):
        with pytest.raises(ValueError, match="Not a URL"):
            Attachment.from_url(str(tmp_path / "image.png"))

    def test_exported_from_railtracks_llm(self):
        import railtracks.llm as llm

        assert llm.Attachment is Attachment


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

    def test_accepts_attachment_objects(self):
        audio = Attachment.from_bytes(_WAV, filename="call.wav")

        single = UserMessage("Transcribe", attachment=audio)
        mixed = UserMessage("Compare", attachment=("https://example.com/a.png", audio))

        assert single.attachment == [audio]
        assert single.attachment[0] is audio
        assert mixed.attachment is not None
        assert [a.type for a in mixed.attachment] == ["url", "data_uri"]
        assert mixed.attachment[1] is audio

    def test_encode_keeps_the_session_record_shape(self, tmp_path):
        """The session JSON reads `encode()`; new sources must keep its shape and stay payload-free."""
        image_file = tmp_path / "chart.png"
        image_file.write_bytes(_PNG)
        message = UserMessage(
            "Compare",
            attachment=[
                str(image_file),
                "https://example.com/a.png",
                Attachment.from_bytes(_WAV, filename="call.wav"),
            ],
        )

        assert message.encode() == {
            "role": "user",
            "content": [
                {"type": "text", "text": "Compare"},
                {"modality": "image", "type": "local", "info": str(image_file)},
                {
                    "modality": "image",
                    "type": "url",
                    "info": "https://example.com/a.png",
                },
                {"modality": "audio", "type": "data_uri", "info": "..."},
            ],
        }


# =================================== END UserMessage Attachments Tests ==================================


# =================================== START ToolCalls Content Tests ==================================
class TestToolCallsContent:
    """A tool-calling turn carries the calls AND whatever the model said with them."""

    @pytest.fixture
    def call(self):
        return ToolCall(identifier="id1", name="example_tool", arguments={"foo": 1})

    def test_holds_text_alongside_the_calls(self, call):
        content = ToolCalls([call], text="I will call example_tool for you.")
        assert list(content) == [call]
        assert content.text == "I will call example_tool for you."

    def test_text_defaults_to_none(self, call):
        assert ToolCalls([call]).text is None

    def test_behaves_as_a_list_of_tool_calls(self, call):
        content = ToolCalls([call], text="prose")
        assert isinstance(content, list)
        assert len(content) == 1
        assert content[0] is call
        assert list(content) == [call]
        assert content == [call]  # equality stays list equality

    def test_deepcopy_preserves_text(self, call):
        content = deepcopy(ToolCalls([call], text="prose"))
        assert isinstance(content, ToolCalls)
        assert content.text == "prose"

    def test_assistant_message_normalizes_a_plain_list(self, call):
        """Passing a bare list of tool calls still works, and becomes a ToolCalls."""
        message = AssistantMessage(content=[call])
        assert isinstance(message.content, ToolCalls)
        assert message.content.text is None
        assert message.tool_calls == [call]

    def test_assistant_message_keeps_a_tool_calls_as_is(self, call):
        content = ToolCalls([call], text="prose")
        assert AssistantMessage(content=content).content is content

    def test_encode_surfaces_the_text(self, call):
        encoded = AssistantMessage(content=ToolCalls([call], text="prose")).encode()
        assert encoded["text"] == "prose"

    def test_encode_omits_text_when_there_is_none(self, call):
        assert "text" not in AssistantMessage(content=[call]).encode()
        assert "text" not in AssistantMessage(content="hi").encode()


# =================================== END ToolCalls Content Tests ==================================
