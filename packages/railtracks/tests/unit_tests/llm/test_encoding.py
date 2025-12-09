import base64
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pytest

from railtracks.llm.encoding import detect_source, encode, ensure_data_uri, _is_base64_image
from railtracks.llm.image_formats import detect_image_mime_from_bytes


class TestDetectSource:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA", "data_uri"),
            ("data:image/jpeg;base64,/9j/4AAQSkZJRg", "data_uri"),
            ("http://example.com/image.png", "url"),
            ("https://example.com/image.png", "url"),
            ("ftp://example.com/image.png", "url"),
            ("ftps://example.com/image.png", "url"),
            ("/path/to/image.png", "local"),
            ("file:///path/to/image.png", "local"),
            ("images/photo.jpg", "local"),
            ("./local/image.png", "local"),
            ("../images/photo.jpg", "local"),
            ("~/images/photo.jpg", "local"),
        ],
    )
    def test_detect_source_types(self, path, expected):
        assert detect_source(path) == expected

    @patch("os.name", "nt")
    def test_detect_windows_forward_slash(self):
        assert detect_source("C:/Users/image.png") == "local"

    @patch("os.name", "nt")
    def test_detect_windows_backslash(self):
        assert detect_source("C:\\Users\\image.png") == "local"

    @patch("os.name", "nt")
    def test_detect_windows_unc_path(self):
        assert detect_source("\\\\server\\share\\image.png") == "local"

    def test_invalid_scheme_raises_error(self):
        with pytest.raises(ValueError, match="Could not determine image source type"):
            detect_source("invalid://example.com/image.png")

    def test_detect_source_relative_path_with_spaces(self):
        assert detect_source("images/my photo.jpg") == "local"


class TestEncode:
    def test_encode_local_file(self, tmp_path):
        image_data = b"fake image data"
        image_file = tmp_path / "test.png"
        image_file.write_bytes(image_data)

        result = encode(str(image_file))
        assert result == base64.b64encode(image_data).decode("utf-8")

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="File not found"):
            encode("/nonexistent/file.png")

    def test_path_is_directory(self, tmp_path):
        directory = tmp_path / "test_dir"
        directory.mkdir()
        with pytest.raises(ValueError, match="Path is not a file"):
            encode(str(directory))

    @patch("railtracks.llm.encoding.request.urlopen")
    def test_encode_url(self, mock_urlopen):
        image_data = b"url image data"
        mock_response = Mock()
        mock_response.read.return_value = image_data
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = encode("https://example.com/image.png")
        assert result == base64.b64encode(image_data).decode("utf-8")

    @patch("railtracks.llm.encoding.request.urlopen")
    def test_url_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError("http://example.com", 404, "Not Found", None, None)  # type: ignore
        with pytest.raises(ValueError, match="Failed to encode URL"):
            encode("http://example.com/image.png")

    def test_data_uri_raises_error(self):
        with pytest.raises(ValueError, match="Data is already in byte64 encoded format"):
            encode("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA")

    def test_empty_file_raises_error(self, tmp_path):
        empty_file = tmp_path / "empty.png"
        empty_file.write_bytes(b"")
        with pytest.raises(ValueError, match="Failed to encode image"):
            encode(str(empty_file))

    def test_encode_binary_roundtrip(self, tmp_path):
        binary_data = bytes(range(256))
        binary_file = tmp_path / "binary.dat"
        binary_file.write_bytes(binary_data)

        result = encode(str(binary_file))
        decoded = base64.b64decode(result)
        assert decoded == binary_data

    @pytest.mark.parametrize(
        "extension,header",
        [
            ("png", b"\x89PNG\r\n\x1a\n"),
            ("jpg", b"\xff\xd8\xff"),
            ("gif", b"GIF89a"),
            ("webp", b"RIFF"),
        ],
    )
    def test_different_formats(self, tmp_path, extension, header):
        image_file = tmp_path / f"image.{extension}"
        image_file.write_bytes(header)
        result = encode(str(image_file))
        assert result == base64.b64encode(header).decode("utf-8")

    def test_encode_non_image_binary(self, tmp_path):
        non_image_file = tmp_path / "random.bin"
        non_image_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")
        result = encode(str(non_image_file))
        assert result == base64.b64encode(b"\x00\x01\x02\x03\x04\x05").decode("utf-8")


class TestAdditionalEncodingCases:
    def test_ensure_data_uri_valid_data_uri(self):
        uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
        assert ensure_data_uri(uri).startswith("data:image/png;base64,")

    def test_ensure_data_uri_invalid_header(self):
        bad_uri = "data:image/png;base64iVBORw0KGgoAAAANSUhEUgAAAAUA"
        with pytest.raises(ValueError, match="Incomplete data URI"):
            ensure_data_uri(bad_uri)

    def test_ensure_data_uri_plain_base64(self):
        png_bytes = b"\x89PNG\r\n\x1a\n"
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        result = ensure_data_uri(b64)
        assert result.startswith("data:image/png;base64,")

    def test_ensure_data_uri_invalid_base64(self):
        with pytest.raises(ValueError, match="Provided string is not valid base64"):
            ensure_data_uri("not_base64!!")

    def test_is_base64_image_invalid(self):
        assert not _is_base64_image("not_base64!!")

    def test_is_base64_image_valid_non_image(self):
        # base64 for "hello world" (not an image)
        b64 = base64.b64encode(b"hello world").decode("utf-8")
        assert not _is_base64_image(b64)

    def test_detect_image_mime_from_bytes_unsupported(self):
        # Should return None for random bytes
        assert detect_image_mime_from_bytes(b"abcdefg") is None

