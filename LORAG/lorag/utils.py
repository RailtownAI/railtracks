"""
Utility functions for the LORAG system.
"""

import os
import glob
from typing import List, Dict, Any, Optional, Union, Tuple
import tiktoken

class LORAGTokenizer:
    def __init__(self, token_encoding:str="cl100k_base"):
        self.token_encoding = token_encoding
        self.tokenizer = tiktoken.get_encoding(token_encoding)
        
    def decode(self, tokens:Union[str, List[int]]) -> str:
        """ Detokenize a list of tokens into text.
        """
        return self.tokenizer.decode(tokens)

    def encode(self, text:str) -> List[int]:
        """ Tokenize a string into a list of tokens.
        """
        return self.tokenizer.encode(text)
    def get_token_count(self, text:str) -> int:
        """ Get the number of tokens in a string.
        """
        return len(self.encode(text))

def list_files(directory: str, extensions: Optional[List[str]] = None, recursive: bool = True) -> List[str]:
    """List files in a directory.
    
    Args:
        directory: Directory to list files from
        extensions: List of file extensions to include (e.g., ['.txt', '.md'])
        recursive: Whether to search recursively
        
    Returns:
        List of file paths
    """
    # Ensure directory exists
    if not os.path.isdir(directory):
        raise ValueError(f"Directory not found: {directory}")
    
    # Set up search pattern
    if recursive:
        pattern = os.path.join(directory, '**')
    else:
        pattern = os.path.join(directory, '*')
    
    # Get all files
    all_files = []
    
    if recursive:
        for root, _, files in os.walk(directory):
            for file in files:
                all_files.append(os.path.join(root, file))
    else:
        all_files = glob.glob(pattern)
        all_files = [f for f in all_files if os.path.isfile(f)]
    
    # Filter by extension if specified
    if extensions:
        filtered_files = []
        for file in all_files:
            ext = os.path.splitext(file)[1].lower()
            if ext in extensions:
                filtered_files.append(file)
        return filtered_files
    
    return all_files


def read_file(file_path: str) -> str:
    """Read a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File content
    """
    # Ensure file exists
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Read file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return content


def write_file(file_path: str, content: str) -> None:
    """Write content to a file.
    
    Args:
        file_path: Path to the file
        content: Content to write
    """
    # Create directory if it doesn't exist
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    
    # Write file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get information about a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary containing file information
    """
    # Ensure file exists
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Get file information
    file_info = {
        'name': os.path.basename(file_path),
        'path': file_path,
        'size': os.path.getsize(file_path),
        'modified': os.path.getmtime(file_path),
        'extension': os.path.splitext(file_path)[1].lower()
    }
    
    return file_info