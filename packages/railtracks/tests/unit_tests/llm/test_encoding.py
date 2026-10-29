import base64
import http.client
import io
from unittest.mock import Mock, patch

import pytest
from railtracks.llm._url_fetch import _READ_CHUNK_BYTES
from railtracks.llm.attachment_formats import (
    detect_attachment_mime_from_bytes,
    detect_image_mime_from_bytes,
)
from railtracks.llm.encoding import (
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
    def _mock_response(mock_open, body: bytes, status: int = 200) -> Mock:
        response = Mock()
        response.status = status
        response.read.side_effect = io.BytesIO(body).read
        response.length = None
        mock_open.return_value = (Mock(), response)
        return response

    @staticmethod
    def _http_response(mock_open, raw: bytes) -> http.client.HTTPResponse:
        """A real `HTTPResponse` parsed from `raw`, read through a `BufferedReader` like a socket."""

        class _Sock:
            def makefile(self, mode: str) -> io.BufferedReader:
                return io.BufferedReader(io.BytesIO(raw))

        response = http.client.HTTPResponse(_Sock())  # type: ignore[arg-type]
        response.begin()
        mock_open.return_value = (Mock(), response)
        return response

    @patch("railtracks.llm._url_fetch._open")
    def test_encode_url(self, mock_open):
        image_data = b"url image data"
        self._mock_response(mock_open, image_data)

        result = encode("https://example.com/image.png")
        assert result == base64.b64encode(image_data).decode("utf-8")

    @patch("railtracks.llm._url_fetch._open")
    def test_url_over_size_limit_raises(self, mock_open):
        self._mock_response(mock_open, b"x" * (1024 * 1024 + 1))

        with pytest.raises(ValueError, match="exceeds the 1.0 MB limit"):
            encode("https://example.com/report.pdf", max_mb=1.0)

    @patch("railtracks.llm._url_fetch._open")
    def test_url_at_size_limit_is_encoded(self, mock_open):
        body = b"x" * (1024 * 1024)
        self._mock_response(mock_open, body)

        result = encode("https://example.com/report.pdf", max_mb=1.0)

        assert base64.b64decode(result) == body

    @patch("railtracks.llm._url_fetch._open")
    def test_url_read_is_bounded(self, mock_open):
        """Every read passes a chunk size, so neither an endless body nor a large cap allocates up front."""
        response = self._mock_response(mock_open, b"x" * (3 * _READ_CHUNK_BYTES))

        encode("https://example.com/report.pdf", max_mb=1.0)

        sizes = [c.args[0] for c in response.read.call_args_list]
        assert len(sizes) > 1
        assert all(0 < size <= _READ_CHUNK_BYTES for size in sizes)

    @patch("railtracks.llm._url_fetch._open")
    def test_url_without_content_length_and_large_cap(self, mock_open):
        """A close-delimited body under a huge cap is read without reserving the cap in memory."""
        body = b"%PDF-1.4 tiny"
        self._http_response(mock_open, b"HTTP/1.0 200 OK\r\n\r\n" + body)

        result = encode("https://example.com/report.pdf", max_mb=1_000_000)

        assert base64.b64decode(result) == body

    @patch("railtracks.llm._url_fetch._open")
    def test_url_truncated_body_raises(self, mock_open):
        self._http_response(
            mock_open,
            b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n%PDF-1.4 cut",
        )

        with pytest.raises(ValueError, match="988 bytes short of its Content-Length"):
            encode("https://example.com/report.pdf")

    @patch("railtracks.llm._url_fetch._open")
    def test_url_truncated_chunked_body_raises(self, mock_open):
        self._http_response(
            mock_open,
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n64\r\n%PDF-1.4",
        )

        with pytest.raises(ValueError, match="ended early"):
            encode("https://example.com/report.pdf")

    @patch("railtracks.llm._url_fetch._open")
    def test_url_complete_body_with_content_length(self, mock_open):
        body = b"%PDF-1.4 whole"
        self._http_response(
            mock_open,
            b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % len(body) + body,
        )

        assert base64.b64decode(encode("https://example.com/report.pdf")) == body

    @pytest.mark.parametrize("max_mb", [0, -1, float("inf"), float("nan")])
    @patch("railtracks.llm._url_fetch._open")
    def test_max_mb_must_be_positive_and_finite(self, mock_open, max_mb):
        with pytest.raises(
            ValueError, match="max_mb must be a positive, finite number"
        ):
            encode("https://example.com/report.pdf", max_mb=max_mb)
        mock_open.assert_not_called()

    def test_local_file_is_not_size_limited(self, tmp_path):
        local = tmp_path / "big.pdf"
        local.write_bytes(b"x" * (1024 * 1024 + 1))

        result = encode(str(local), max_mb=1.0)

        assert len(base64.b64decode(result)) == 1024 * 1024 + 1

    @patch("railtracks.llm._url_fetch._open")
    def test_url_http_error(self, mock_open):
        self._mock_response(mock_open, b"", status=404)
        with pytest.raises(
            ValueError, match="HTTP 404 from http://example.com/image.png"
        ):
            encode("http://example.com/image.png?sig=secret")

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

    def test_ensure_data_uri_restores_missing_padding(self):
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 9
        unpadded = base64.b64encode(png_bytes).decode("utf-8").rstrip("=")

        result = ensure_data_uri(unpadded)

        payload = result.split(",", 1)[1]
        assert len(payload) % 4 == 0
        assert base64.b64decode(payload, validate=True) == png_bytes

    def test_ensure_data_uri_strips_line_wrapping(self):
        png_bytes = b"\x89PNG\r\n\x1a\n" + bytes(range(64))
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        wrapped = "\n".join(b64[i : i + 20] for i in range(0, len(b64), 20))

        result = ensure_data_uri(wrapped)

        payload = result.split(",", 1)[1]
        assert base64.b64decode(payload, validate=True) == png_bytes

    def test_detect_source_accepts_wrapped_unpadded_base64(self):
        png_bytes = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 3
        b64 = base64.b64encode(png_bytes).decode("utf-8").rstrip("=")
        wrapped = "\n".join(b64[i : i + 76] for i in range(0, len(b64), 76))

        assert detect_source(wrapped) == "data_uri"
        payload = ensure_data_uri(wrapped).split(",", 1)[1]
        assert base64.b64decode(payload, validate=True) == png_bytes

    def test_ensure_data_uri_converts_urlsafe_alphabet(self):
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\xfb\xff" * 30
        urlsafe = base64.urlsafe_b64encode(png_bytes).decode("utf-8")
        assert "-" in urlsafe and "_" in urlsafe

        assert detect_source(urlsafe) == "data_uri"
        payload = ensure_data_uri(urlsafe).split(",", 1)[1]
        assert base64.b64decode(payload, validate=True) == png_bytes


class TestDetectAttachmentMime:
    @pytest.mark.parametrize("brand", [b"avif", b"avis"])
    def test_avif_detected_from_real_header(self, brand):
        header = b"\x00\x00\x00\x1cftyp" + brand + b"\x00\x00\x00\x00mif1miaf"
        assert detect_attachment_mime_from_bytes(header) == "image/avif"

    def test_webp_still_detected(self):
        header = b"RIFF\x24\x00\x00\x00WEBPVP8 "
        assert detect_attachment_mime_from_bytes(header) == "image/webp"

    @pytest.mark.parametrize(
        "data",
        [
            b"ftypavif\x00\x00\x00\x00",
            b"\x00\x00\x00\x1cftypav",
            b"RIFF\x24\x00\x00\x00WEB",
        ],
        ids=["ftyp_at_start", "truncated_avif", "truncated_webp"],
    )
    def test_misplaced_or_truncated_headers_are_not_detected(self, data):
        assert detect_attachment_mime_from_bytes(data) is None
