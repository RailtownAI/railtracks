import base64
import os
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal


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
    
    if not parsed.scheme or parsed.scheme == "file" or (len(parsed.scheme) == 1 and os.name == 'nt'):
        return "local"
    
    raise ValueError(f"Could not determine image source type for: {path}")


def encode_image(image_path: str) -> str:
    """Encodes a local image file to a Base64 string.
    
    Args:
        image_path (str): The path to the local image file.
        
    Returns:
        str: Base64 encoded string of the image.
        
    Raises:
        FileNotFoundError: If the image file doesn't exist.
        ValueError: If the path is not a local file.
    """
    source_type = detect_source(image_path)
    
    if source_type != "local":
        raise ValueError(f"encode_image() only works with local files. Got: {source_type}")
    
    file_path = Path(image_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {image_path}")
    
    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
    
def decode_image(base64_string, output_path):
    """
    Decodes a Base64 string back to an image file.

    Args:
        base64_string (str): The Base64 encoded string.
        output_path (str): The path to save the decoded image file.
    """
    with open(output_path, "wb") as image_file:
        image_file.write(base64.b64decode(base64_string))

