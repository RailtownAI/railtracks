import base64
import http.client
import io
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pytest
from railtracks.llm.attachment_formats import detect_image_mime_from_bytes
from railtracks.llm.encoding import (
    _READ_CHUNK_BYTES,
    _is_base64_attachment,
    detect_source,
    encode,
    ensure_data_uri,
)


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

    @staticmethod
    def _mock_response(mock_urlopen, body: bytes) -> Mock:
        response = Mock()
        response.read.side_effect = io.BytesIO(body).read
        response.length = None
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = response
        return response

    @staticmethod
    def _http_response(mock_urlopen, raw: bytes) -> http.client.HTTPResponse:
        """A real `HTTPResponse` parsed from `raw`, read through a `BufferedReader` like a socket."""

        class _Sock:
            def makefile(self, mode: str) -> io.BufferedReader:
                return io.BufferedReader(io.BytesIO(raw))

        response = http.client.HTTPResponse(_Sock())  # type: ignore[arg-type]
        response.begin()
        mock_urlopen.return_value = response
        return response

    @patch("railtracks.llm.encoding.request.urlopen")
    def test_encode_url(self, mock_urlopen):
        image_data = b"url image data"
        self._mock_response(mock_urlopen, image_data)

        result = encode("https://example.com/image.png")
        assert result == base64.b64encode(image_data).decode("utf-8")

    @patch("railtracks.llm.encoding.request.urlopen")
    def test_url_over_size_limit_raises(self, mock_urlopen):
        self._mock_response(mock_urlopen, b"x" * (1024 * 1024 + 1))

        with pytest.raises(ValueError, match="exceeds the 1.0 MB limit"):
            encode("https://example.com/report.pdf", max_mb=1.0)

    @patch("railtracks.llm.encoding.request.urlopen")
    def test_url_at_size_limit_is_encoded(self, mock_urlopen):
        body = b"x" * (1024 * 1024)
        self._mock_response(mock_urlopen, body)

        result = encode("https://example.com/report.pdf", max_mb=1.0)

        assert base64.b64decode(result) == body

    @patch("railtracks.llm.encoding.request.urlopen")
    def test_url_read_is_bounded(self, mock_urlopen):
        """Every read passes a chunk size, so neither an endless body nor a large cap allocates up front."""
        response = self._mock_response(mock_urlopen, b"x" * (3 * _READ_CHUNK_BYTES))

        encode("https://example.com/report.pdf", max_mb=1.0)

        sizes = [c.args[0] for c in response.read.call_args_list]
        assert len(sizes) > 1
        assert all(0 < size <= _READ_CHUNK_BYTES for size in sizes)

    @patch("railtracks.llm.encoding.request.urlopen")
    def test_url_without_content_length_and_large_cap(self, mock_urlopen):
        """A close-delimited body under a huge cap is read without reserving the cap in memory."""
        body = b"%PDF-1.4 tiny"
        self._http_response(mock_urlopen, b"HTTP/1.0 200 OK\r\n\r\n" + body)

        result = encode("https://example.com/report.pdf", max_mb=1_000_000)

        assert base64.b64decode(result) == body

    @patch("railtracks.llm.encoding.request.urlopen")
    def test_url_truncated_body_raises(self, mock_urlopen):
        self._http_response(
            mock_urlopen,
            b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n%PDF-1.4 cut",
        )

        with pytest.raises(ValueError, match="988 bytes short of its Content-Length"):
            encode("https://example.com/report.pdf")

    @patch("railtracks.llm.encoding.request.urlopen")
    def test_url_complete_body_with_content_length(self, mock_urlopen):
        body = b"%PDF-1.4 whole"
        self._http_response(
            mock_urlopen,
            b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % len(body) + body,
        )

        assert base64.b64decode(encode("https://example.com/report.pdf")) == body

    @pytest.mark.parametrize("max_mb", [0, -1, float("inf"), float("nan")])
    @patch("railtracks.llm.encoding.request.urlopen")
    def test_max_mb_must_be_positive_and_finite(self, mock_urlopen, max_mb):
        with pytest.raises(
            ValueError, match="max_mb must be a positive, finite number"
        ):
            encode("https://example.com/report.pdf", max_mb=max_mb)
        mock_urlopen.assert_not_called()

    def test_local_file_is_not_size_limited(self, tmp_path):
        local = tmp_path / "big.pdf"
        local.write_bytes(b"x" * (1024 * 1024 + 1))

        result = encode(str(local), max_mb=1.0)

        assert len(base64.b64decode(result)) == 1024 * 1024 + 1

    @patch("railtracks.llm.encoding.request.urlopen")
    def test_url_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "http://example.com", 404, "Not Found", None, None
        )  # type: ignore
        with pytest.raises(ValueError, match="Failed to encode URL"):
            encode("http://example.com/image.png")

    def test_data_uri_raises_error(self):
        with pytest.raises(
            ValueError, match="Data is already in byte64 encoded format"
        ):
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

    def test_is_base64_attachment_invalid(self):
        assert not _is_base64_attachment("not_base64!!")

    def test_is_base64_attachment_valid_non_attachment(self):
        # base64 for "hello world" (not an image or PDF)
        b64 = base64.b64encode(b"hello world").decode("utf-8")
        assert not _is_base64_attachment(b64)

    def test_is_base64_attachment_pdf(self):
        # PDF magic bytes are recognized as a valid attachment
        b64 = base64.b64encode(b"%PDF-1.4\n%\xc2\xa5\xc2\xb1\xc3\xab").decode("utf-8")
        assert _is_base64_attachment(b64)

    def test_detect_image_mime_from_bytes_unsupported(self):
        # Should return None for random bytes
        assert detect_image_mime_from_bytes(b"abcdefg") is None
