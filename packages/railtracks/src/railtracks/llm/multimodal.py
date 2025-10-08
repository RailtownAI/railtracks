import base64
import os
from pathlib import Path
from typing import Literal
from urllib import error, request
from urllib.parse import urlparse


def detect_source(path: str) -> Literal["local", "url", "data_uri"]:
    """Detects whether the image path is a local file, URL, or data URI.

    Args:
        path (str): The path/URL to check.

    Returns:
        str: One of "local", "url", or "data_uri"

    Raises:
        ValueError: If the path is invalid or cannot be determined.
    """

    if path.startswith("data:"):
        return "data_uri"

    parsed = urlparse(path)

    if parsed.scheme in ("http", "https", "ftp", "ftps"):
        return "url"

    if (
        not parsed.scheme
        or parsed.scheme == "file"
        or (len(parsed.scheme) == 1 and os.name == "nt")
    ):
        return "local"

    raise ValueError(f"Could not determine image source type for: {path}")


def encode(path: str) -> str:
    """Encodes image/audio loocated at path to a Base64 string.

    Args:
        path (str): The path to the local image file.

    Returns:
        str: Base64 encoded string

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the path is not a local file.
    """
    source_type = detect_source(path)

    encoding = ""

    match source_type:
        case "local":
            file_path = Path(path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            if not file_path.is_file():
                raise ValueError(f"Path is not a file: {path}")
            with open(path, "rb") as image_file:
                encoding = base64.b64encode(image_file.read()).decode("utf-8")
        case (
            "url"
        ):  # we will not encode urls for now but putting this here for future proofing
            try:
                with request.urlopen(path) as url:
                    encoding = base64.b64encode(url.read()).decode("utf-8")
            except error.HTTPError as e:
                raise ValueError(f"Failed to encode URL: {path}. Error: {e}")
        case "data_uri":
            raise ValueError("Data is already in byte64 encoded format.")
        case _:
            raise ValueError(f"Unsupported source type: {source_type}")

    if not encoding:
        raise ValueError("Failed to encode image.")
    else:
        return encoding


def decode_image(base64_string, output_path):
    """
    Decodes a Base64 string back to an image file.

    Args:
        base64_string (str): The Base64 encoded string.
        output_path (str): The path to save the decoded image file.
    """
    with open(output_path, "wb") as image_file:
        image_file.write(base64.b64decode(base64_string))


if __name__ == "__main__":
    # Example usage
    image_path = "https://cdn.britannica.com/39/226539-050-D21D7721/Portrait-of-a-cat-with-whiskers-visible.jpg"  # Replace with your image path
    print(encode(image_path)[:20])
    # image_path = "image.png"
    print(encode("image.png")[:20])
