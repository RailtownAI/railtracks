import base64
import pytest
from encode_images import ensure_data_uri

def _to_b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")

def test_png_detection():
    png_header = b'\x89PNG\r\n\x1a\n' + b'0000'
    b64 = _to_b64(png_header)
    uri = ensure_data_uri(b64)
    assert uri.startswith("data:image/png;base64,")

def test_jpeg_detection():
    jpeg_header = b'\xff\xd8\xff\xdb' + b'0000'
    b64 = _to_b64(jpeg_header)
    uri = ensure_data_uri(b64)
    assert uri.startswith("data:image/jpeg;base64,")

def test_gif_detection():
    gif_header = b'GIF89a' + b'0000'
    b64 = _to_b64(gif_header)
    uri = ensure_data_uri(b64)
    assert uri.startswith("data:image/gif;base64,")

def test_webp_detection():
    # RIFF....WEBP
    webp_header = b'RIFF' + (b'\x00\x00\x00\x00') + b'WEBP' + b'VP8 ' + b'000'
    b64 = _to_b64(webp_header)
    uri = ensure_data_uri(b64)
    assert uri.startswith("data:image/webp;base64,")

def test_accepts_full_data_uri():
    sample_b64 = _to_b64(b'\xff\xd8\xff\xdb' + b'0000')
    full = "data:image/jpeg;base64," + sample_b64
    assert ensure_data_uri(full).startswith("data:image/jpeg;base64,")

def test_malformed_data_uri_rejected():
    with pytest.raises(ValueError):
        ensure_data_uri("data:image/unknown;base64,abcd")

def test_invalid_base64_rejected():
    with pytest.raises(ValueError):
        ensure_data_uri("not-a-valid-base64!!")
