import base64
import os
import io
from PIL import Image
from typing import Union, Optional, Dict, Any
from openai import OpenAI
    
def upload_image(source: Union[str, bytes, io.BytesIO]) -> str:
    """
    Upload an image from a file path, bytes, or BytesIO object and return base64 encoding.
    
    Args:
        source (Union[str, bytes, io.BytesIO]): Image source - can be a file path, 
                                                    bytes, or BytesIO object
    
    Returns:
        str: Base64 encoded image string
    """
    if isinstance(source, str):
        # Source is a file path
        print(f"Loading image from {source}")
        with open(source, "rb") as image_file:
            image_bytes = image_file.read()
    elif isinstance(source, bytes):
        # Source is already bytes
        image_bytes = source
    elif isinstance(source, io.BytesIO):
        # Source is a BytesIO object
        image_bytes = source.getvalue()
    else:
        raise TypeError("Source must be a file path, bytes, or BytesIO object")
    
    # Encode to base64
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    print("Image successfully uploaded and encoded")
    return base64_image

def parse_image_to_text(image_source: Union[str, bytes, io.BytesIO]) -> str:
    """
    Extract text from an image using OpenAI's API.
    
    Args:
        image_source (Union[str, bytes, io.BytesIO]): Image to parse - can be a file path,
                                                        bytes, or BytesIO object
    
    Returns:
        str: Extracted text from the image
    """
    client = OpenAI()
    base64_image = upload_image(image_source)
    
    print("Parsing image to text...")
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all text from this image."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    )
    
    extracted_text = response.choices[0].message.content
    print("Text extraction complete")
    return extracted_text

def parse_image_to_mermaid(image_source: Union[str, bytes, io.BytesIO]) -> str:
    """
    Convert a diagram image to Mermaid code using OpenAI's API.
    
    Args:
        image_source (Union[str, bytes, io.BytesIO]): Image to parse - can be a file path,
                                                        bytes, or BytesIO object
    
    Returns:
        str: Mermaid code representation of the diagram
    """
    client = OpenAI()
    base64_image = upload_image(image_source)
    
    print("Parsing image to Mermaid code...")
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Convert this diagram to Mermaid code. Only provide the code without any explanation, making sure it's valid Mermaid syntax."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    )
    
    mermaid_code = response.choices[0].message.content
    # Clean up the response to extract just the mermaid code
    if "```mermaid" in mermaid_code:
        mermaid_code = mermaid_code.split("```mermaid")[1]
        if "```" in mermaid_code:
            mermaid_code = mermaid_code.split("```")[0]
    
    print("Mermaid code generation complete")
    return mermaid_code.strip()

def save_image(image_data: Union[str, bytes, io.BytesIO], 
                filename: str, 
                is_base64: bool = False) -> str:
    """
    Save image data to a file.
    
    Args:
        image_data (Union[str, bytes, io.BytesIO]): Image data to save
        filename (str): Output filename
        is_base64 (bool): Whether the image_data is a base64 string
    
    Returns:
        str: Path to the saved image file
    """
    if is_base64 and isinstance(image_data, str):
        # Convert base64 string to bytes
        image_bytes = base64.b64decode(image_data)
    elif isinstance(image_data, str):
        # Assume it's a file path
        with open(image_data, "rb") as f:
            image_bytes = f.read()
    elif isinstance(image_data, io.BytesIO):
        image_bytes = image_data.getvalue()
    else:
        # Assume it's already bytes
        image_bytes = image_data
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(filename)) or '.', exist_ok=True)
    
    # Save the file
    with open(filename, "wb") as f:
        f.write(image_bytes)
    
    print(f"Image saved to {filename}")
    return filename

def analyze_image(image_source: Union[str, bytes, io.BytesIO], 
                analysis_prompt: str = "What's in this image?") -> Dict[str, Any]:
    """
    Perform a general analysis of an image using OpenAI's API.
    
    Args:
        image_source (Union[str, bytes, io.BytesIO]): Image to analyze
        analysis_prompt (str): The question or prompt to ask about the image
    
    Returns:
        Dict[str, Any]: Analysis results
    """
    client = OpenAI()
    base64_image = upload_image(image_source)
    
    print("Analyzing image...")
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": analysis_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    )
    
    analysis = response.choices[0].message.content
    
    result = {
        "analysis": analysis,
        "model": "gpt-4.1",
        "prompt": analysis_prompt
    }
    
    print("Image analysis complete")
    return result

# Example usage
if __name__ == "__main__":
    # Initialize the processor
    
    # Example: Upload and analyze an image
    image_path = "demo/assets/mermaid.jpeg"
    
    # Upload and parse to text
    extracted_text = parse_image_to_text(image_path)
    print(f"Extracted Text: {extracted_text}")
    
    # Upload and parse to mermaid
    mermaid_code = parse_image_to_mermaid(image_path)
    print(f"Mermaid Code: {mermaid_code}")
    
    # Save the image to a new location
    saved_path = save_image(image_path, "output/saved_image.jpg")
    
    # General analysis
    analysis_result = analyze_image(image_path, "Describe the content of this image in detail")
    print(f"Analysis: {analysis_result['analysis']}")