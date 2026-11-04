import base64
import hashlib
from copy import deepcopy

import pytest
from railtracks.llm import UserMessage
from railtracks.llm.message import Attachment

# PNG magic bytes, then bytes whose base64 uses "+" and "/", which URL-safe base64 swaps.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\xfb\xff\xfe" * 7
PNG_SHA256 = hashlib.sha256(PNG_BYTES).hexdigest()


class _Sink:
    def __init__(self):
        self.saved: list[tuple[str, int, bytes]] = []

    def save(self, sha256, size, data):
        self.saved.append((sha256, size, data()))


@pytest.fixture
def png_path(tmp_path):
    path = tmp_path / "before.png"
    path.write_bytes(PNG_BYTES)
    return str(path)


class TestAttachmentHash:
    def test_same_bytes_hash_the_same_from_every_source(self, png_path):
        b64 = base64.b64encode(PNG_BYTES).decode()
        urlsafe_unpadded = base64.urlsafe_b64encode(PNG_BYTES).decode().rstrip("=")
        sources = [
            png_path,
            b64,
            f"data:image/png;base64,{b64}",
            f"data:image/png;base64,{urlsafe_unpadded}",
        ]

        for source in sources:
            attachment = Attachment(source)
            assert attachment.sha256 == PNG_SHA256, source
            assert attachment.size == len(PNG_BYTES), source

    def test_pdf_url_is_hashed_from_the_downloaded_bytes(self, monkeypatch):
        pdf_bytes = b"%PDF-1.4\n%fake pdf body\n%%EOF"
        monkeypatch.setattr(
            "railtracks.llm.message.encode",
            lambda url, **_: base64.b64encode(pdf_bytes).decode(),
        )

        attachment = Attachment("https://example.com/doc.pdf", trust_urls=True)

        assert attachment.sha256 == hashlib.sha256(pdf_bytes).hexdigest()
        assert attachment.size == len(pdf_bytes)

    def test_image_url_has_no_hash(self):
        attachment = Attachment("https://example.com/cat.png")
        assert attachment.sha256 is None
        assert attachment.size is None

    def test_malformed_data_uri_payload_has_no_hash(self):
        attachment = Attachment("data:image/png;base64,abcde")
        assert attachment.sha256 is None
        assert attachment.size is None

    def test_hash_survives_deepcopy(self, png_path):
        copied = deepcopy(Attachment(png_path))
        assert copied.sha256 == PNG_SHA256
        assert copied.size == len(PNG_BYTES)


class TestAttachmentRecord:
    def test_local_file(self, png_path):
        sink = _Sink()

        part = Attachment(png_path).record(sink)

        assert part == {
            "type": "image",
            "mime_type": "image/png",
            "filename": "before.png",
            "source": "path",
            "path": png_path,
            "sha256": PNG_SHA256,
            "size": len(PNG_BYTES),
        }
        assert sink.saved == [(PNG_SHA256, len(PNG_BYTES), PNG_BYTES)]

    def test_inline_data_has_no_reference(self):
        b64 = base64.b64encode(PNG_BYTES).decode()

        sink = _Sink()

        part = Attachment(f"data:image/png;base64,{b64}").record(sink)

        assert part["source"] == "inline"
        assert part["filename"] is None
        assert part["sha256"] == PNG_SHA256
        assert "path" not in part and "url" not in part
        assert b64 not in str(part)
        assert sink.saved == [(PNG_SHA256, len(PNG_BYTES), PNG_BYTES)]

    def test_image_url_keeps_the_url_and_saves_nothing(self):
        sink = _Sink()

        part = Attachment("https://example.com/cat.png").record(sink)

        assert part["source"] == "url"
        assert part["url"] == "https://example.com/cat.png"
        assert part["sha256"] is None
        assert sink.saved == []

    def test_without_a_sink_the_hash_is_still_recorded(self, png_path):
        part = Attachment(png_path).record(None)
        assert part["sha256"] == PNG_SHA256


class TestUserMessageRecord:
    def test_attachments_become_media_parts_after_the_text(self, png_path):
        message = UserMessage(
            "describe", attachment=[png_path, "https://example.com/cat.png"]
        )

        sink = _Sink()

        recorded = message.record(sink)

        assert recorded["role"] == "user"
        text, local, url = recorded["content"]
        assert text == {"type": "text", "text": "describe"}
        assert local["source"] == "path" and url["source"] == "url"
        assert sink.saved == [(PNG_SHA256, len(PNG_BYTES), PNG_BYTES)]

    def test_without_attachments_matches_encode(self):
        message = UserMessage("just text")
        assert message.record(_Sink()) == message.encode()

    def test_encode_is_unchanged(self, png_path):
        message = UserMessage("describe", attachment=png_path)

        assert message.encode() == {
            "role": "user",
            "content": [
                {"type": "text", "text": "describe"},
                {"modality": "image", "type": "local", "info": png_path},
            ],
        }
