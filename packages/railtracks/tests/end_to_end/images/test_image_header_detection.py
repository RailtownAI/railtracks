import base64
import pytest
from pathlib import Path


from railtracks.llm.message import UserMessage
from railtracks.llm.encoding import ensure_data_uri

def make_png_base64():
    # Minimal PNG header + some bytes
    return base64.b64encode(b"\x89PNG\r\n\x1a\n123456").decode("utf-8")

# Supported extensions for the test folder
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico", ".avif"]

def get_image_files(images_dir):
    # Use the absolute path from the repo root for safety
    repo_root = Path(__file__).parents[5]  # Adjust depth if needed
    images_path = repo_root / "packages" / "railtracks" / "tests" / "end_to_end" / "images"
    if not images_path.exists():
        return []
    return [
        f for f in images_path.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]

@pytest.mark.parametrize("image_file", get_image_files("images"))
def test_user_message_with_local_file(image_file):
    msg = UserMessage(content="desc", attachment=str(image_file))
    att = msg.attachment[0]
    assert att.type == "local"
    assert att.encoding.startswith("data:image/")
    # Check that the encoding is valid base64
    header, b64 = att.encoding.split(",", 1)
    base64.b64decode(b64)

@pytest.mark.parametrize("image_file", get_image_files("images"))
def test_user_message_with_base64(image_file):
    with open(image_file, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    msg = UserMessage(content="desc", attachment=b64)
    att = msg.attachment[0]
    assert att.type == "data_uri"
    assert att.encoding.startswith("data:image/")
    header, b64_out = att.encoding.split(",", 1)
    base64.b64decode(b64_out)

@pytest.mark.parametrize("image_file", get_image_files("images"))
def test_user_message_with_data_uri(image_file):
    with open(image_file, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = image_file.suffix.lower().lstrip(".")
    # Map extensions to mime types for test
    mime_map = {
        "jpg": "jpeg",
        "jpeg": "jpeg",
        "png": "png",
        "gif": "gif",
        "webp": "webp",
        "bmp": "bmp",
        "svg": "svg+xml",
        "ico": "x-icon",
        "avif": "avif",
    }
    mime = mime_map.get(ext, ext)
    data_uri = f"data:image/{mime};base64,{b64}"
    msg = UserMessage(content="desc", attachment=data_uri)
    att = msg.attachment[0]
    assert att.type == "data_uri"
    assert att.encoding == ensure_data_uri(data_uri)
    header, b64_out = att.encoding.split(",", 1)
    base64.b64decode(b64_out)

def test_user_message_with_plain_base64():
    b64 = make_png_base64()
    msg = UserMessage(content="desc", attachment=b64)
    assert msg.attachment is not None
    att = msg.attachment[0]
    assert att.type == "data_uri"
    assert att.encoding.startswith("data:image/png;base64,")

def test_user_message_with_valid_data_uri():
    b64 = make_png_base64()
    data_uri = f"data:image/png;base64,{b64}"
    msg = UserMessage(content="desc", attachment=data_uri)
    att = msg.attachment[0]
    assert att.type == "data_uri"
    assert att.encoding == ensure_data_uri(data_uri)

def test_user_message_with_invalid_data_uri_header():
    b64 = make_png_base64()
    bad_uri = f"data:image/png;base64{b64}"  # missing comma
    with pytest.raises(ValueError):
        UserMessage(content="desc", attachment=bad_uri)

def test_user_message_with_url(monkeypatch):
    # Patch urlopen to return PNG bytes
    import railtracks.llm.encoding as encoding_mod
    class DummyResponse:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"\x89PNG\r\n\x1a\n123456"
    monkeypatch.setattr(encoding_mod.request, "urlopen", lambda url: DummyResponse())
    msg = UserMessage(content="desc", attachment="https://example.com/img.png")
    att = msg.attachment[0]
    assert att.type == "url"
    assert att.url == "https://example.com/img.png"

def test_user_message_multiple_attachments(tmp_path):
    img_file = tmp_path / "img.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n123456")
    b64 = make_png_base64()
    msg = UserMessage(content="desc", attachment=[str(img_file), b64])
    assert len(msg.attachment) == 2
    assert msg.attachment[0].type == "local"
    assert msg.attachment[1].type == "data_uri"