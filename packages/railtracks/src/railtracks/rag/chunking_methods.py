from typing import List, Union
import tiktoken
import asyncio
from collections import deque
import railtracks as rt

def strict_chunk_file(file_path : str, token_encoding : str | None = None, chunk_size : int = 400, overlap : int = 200) -> List[str]:
    """
    Splits a file into chunks of specified size, with optional tokenization and overlap.

    Args:
        file_path (str): Path to the file to chunk.
        token_encoding (str, optional): Tokenizer encoding name. If None, chunks by character instead of by token.
        chunk_size (int): Size of each chunk (in tokens or characters).
        overlap (int): Number of tokens/characters to overlap between chunks.

    Returns:
        List[str]: List of chunked strings from the file.

    Raises:
        ValueError: If overlap >= chunk_size or chunk_size <= 0 or overlap < 0.
    """
    chunks = []
    buffer = [] if token_encoding else ""
    if overlap >= chunk_size:
        raise ValueError("'overlap' must be smaller than 'chunk_size'.")
    if chunk_size <= 0 or overlap < 0:
        raise ValueError("'chunk_size' must be greater than 0 and 'overlap' must be at least 0 ")

    with open(file_path, 'r', encoding='utf-8') as f:
        if token_encoding:
            tokenizer = tiktoken.get_encoding(token_encoding)
            for line in f:
                buffer.extend(tokenizer.encode(line))
                while len(buffer) >= chunk_size:
                    chunk = tokenizer.decode(buffer[:chunk_size])
                    chunks.append(chunk)
                    buffer = buffer[chunk_size - overlap:]
            if buffer:
                chunks.append(tokenizer.decode(buffer))
        else:
            for line in f:
                buffer += line
                while len(buffer) >= chunk_size:
                    chunks.append(buffer[:chunk_size])
                    buffer = buffer[chunk_size - overlap:]
            if buffer:
                chunks.append(buffer)

    return chunks

def strict_chunk_text(text: str, token_encoding : str | None = None, chunk_size : int = 400, overlap : int = 200) -> List[str]:
    """
    Splits a string into chunks of specified size, with optional tokenization and overlap.

    Args:
        text (str): The text to chunk.
        token_encoding (str, optional): Tokenizer encoding name. If None, chunks by character instead of by token.
        chunk_size (int): Size of each chunk (in tokens or characters).
        overlap (int): Number of tokens/characters to overlap between chunks.

    Returns:
        List[str]: List of chunked strings.

    Raises:
        ValueError: If overlap >= chunk_size or chunk_size <= 0 or overlap < 0.
    """
    chunks = []
    if overlap >= chunk_size:
        raise ValueError("'overlap' must be smaller than 'chunk_size'.")
    if chunk_size <= 0 or overlap < 0:
        raise ValueError("'chunk_size' must be greater than 0 and 'overlap' must be at least 0 ")

    if token_encoding:
        tokenizer = tiktoken.get_encoding(token_encoding)
        buffer = tokenizer.encode(text)
        while len(buffer) >= chunk_size:
            chunk = tokenizer.decode(buffer[:chunk_size])
            chunks.append(chunk)
            buffer = buffer[chunk_size - overlap:]
        if buffer:
            chunks.append(tokenizer.decode(buffer))
    else:
        buffer = text
        while len(buffer) >= chunk_size:
            chunks.append(buffer[:chunk_size])
            buffer = buffer[chunk_size - overlap:]
        if buffer:
            chunks.append(buffer)

    return chunks

def rough_chunk_file(file_path : str, token_encoding : str, chunk_size : int = 400, overlap : int = 200, delta : int = 100, key : List[str] = [".", "?", "!"]) -> List[str]:
    """
    Splits a file into chunks attempting to split at natural boundaries near chunk_size specified.

    Args:
        file_path (str): Path to the file to chunk.
        delta (int): Allowed deviation from chunk_size for boundary search. 
            If there is no natural split point within the given delta, it will split strictly.
        chunk_size (int): Target chunk size.
        overlap (int): Overlap between chunks.

    Returns:
        List[str]: List of chunked strings from the file.

    Raises:
        ValueError: If overlap + delta >= chunk_size or chunk_size <= 0 or overlap < 0 or delta < 1.
    """
    chunks = []
    if overlap + delta >= chunk_size:
        raise ValueError("'overlap' + 'delta' must be smaller than 'chunk_size'.")
    if chunk_size <= 0 or overlap < 0:
        raise ValueError("'chunk_size' must be greater than 0 and 'overlap' must be at least 0 ")
    if delta < 1:
        raise ValueError("'delta' must be at least 1 ")
    
    buffer = ""
    with open(file_path, 'r', encoding='utf-8') as f:
    
        if token_encoding:
            while len(buffer) < chunk_size*4:
                buffer += f.readline()

            chars_per_token = estimate_chars_per_token(buffer, tiktoken.get_encoding(token_encoding))

            for line in f:
                buffer += line
                while len(buffer)/chars_per_token > chunk_size + delta:
                    split_point = find_best_boundary(buffer, chunk_size, tiktoken.get_encoding(token_encoding), delta, key)
                    chunks.append(buffer[:split_point])
                    buffer = buffer[split_point - overlap:]
        
        else:
            for line in f:
                buffer += line
                while len(buffer) > chunk_size + delta:
                    left_of, right_of = find_two_closest_occurrences(buffer, chunk_size, delta=delta, key=key)
                    split_point = get_best_split_point(left_of, right_of, chunk_size)
                    chunks.append(buffer[:split_point])
                    buffer = buffer[split_point - overlap:]
        
        if buffer:
            chunks.append(buffer)
    
    return chunks

def rough_chunk_text(text: str, token_encoding : str, chunk_size : int = 400, overlap : int = 200, delta : int = 100, key : List[str] = [".", "?", "!"]) -> List[str]:
    """
    Roughly splits text into chunks, attempting to split at natural boundaries near chunk_size.

    Args:
        text (str): The text to chunk.
        delta (int): Allowed deviation from chunk_size for boundary search. 
            If there is no natural split point within the given delta, it will split strictly.
        chunk_size (int): Target chunk size.
        overlap (int): Overlap between chunks.

    Returns:
        List[str]: List of chunked strings.

    Raises:
        ValueError: If overlap + delta >= chunk_size or chunk_size <= 0 or overlap < 0 or delta < 1.
    """

    chunks = []
    if overlap + delta >= chunk_size:
        raise ValueError("'overlap' + 'delta' must be smaller than 'chunk_size'.")
    if chunk_size <= 0 or overlap < 0:
        raise ValueError("'chunk_size' must be greater than 0 and 'overlap' must be at least 0 ")
    if delta < 1:   
        raise ValueError("'delta' must be at least 1 ")

    if token_encoding:
        chars_per_token = estimate_chars_per_token(text, tiktoken.get_encoding(token_encoding))
        while len(text)/chars_per_token >= chunk_size:
            split_point = find_best_boundary(text, chunk_size, tiktoken.get_encoding(token_encoding), delta, key)
            chunks.append(text[:split_point])
            text = text[split_point - overlap:]
    
    else:
        while len(text) >= chunk_size:
            left_of,right_of = find_two_closest_occurrences(text, chunk_size, delta=delta, key=key)
            split_point = get_best_split_point(left_of, right_of, chunk_size)
            chunks.append(text[:split_point])
            text = text[split_point - overlap:]

    if text:
        chunks.append(text)
    return chunks

#Based off Chroma implementation
def recursive_chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 200,
    delta: int = 100,
    separators: List[str] = ["\n\n", "\n", ".", "?", "!", " ", ""]
) -> List[str]:
    """
    Recursively splits text into chunks using hierarchical separators.
    """
    if len(text) <= chunk_size:
        return [text]
    
    # Try each separator in order of preference
    for separator in separators:
        if separator in text:
            # Split by this separator
            parts = text.split(separator)
            
            # Rebuild parts with separator (if needed)
            if separator != "":
                parts = [p + separator for p in parts[:-1]] + [parts[-1]]
            
            # Try to merge parts into chunks
            chunks = []
            current_chunk = []
            current_length = 0
            
            for part in parts:
                part_len = len(part)
                
                if current_length + part_len <= chunk_size:
                    current_chunk.append(part)
                    current_length += part_len
                else:
                    # Finalize current chunk
                    if current_chunk:
                        chunk_text = "".join(current_chunk)
                        chunks.append(chunk_text)
                        
                        # Start new chunk with overlap
                        if overlap > 0:
                            overlap_text = chunk_text[-overlap:]
                            current_chunk = [overlap_text, part]
                            current_length = len(overlap_text) + part_len
                        else:
                            current_chunk = [part]
                            current_length = part_len
                    else:
                        # Part is too large, recurse with next separator
                        if part_len > chunk_size:
                            chunks.extend(recursive_chunk_text(
                                part, chunk_size, overlap, delta, 
                                separators[separators.index(separator) + 1:]
                            ))
                        else:
                            current_chunk = [part]
                            current_length = part_len
            
            # Add final chunk
            if current_chunk:
                chunks.append("".join(current_chunk))
            
            return chunks
    
    # Fallback: hard split if no separators work
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    return chunks

#TODO: finish this function by implementing agent class for this
def llm_chunk_text(text: str, agent, window_size: int = 1000) -> List[str]:
    """
    Chunks text using an LLM agent with windowing to handle long documents.
    Protects split boundaries by carrying forward the last split point to the next window.

    Args:
        text (str): The text to chunk.
        agent: The agent used to determine split points.
        window_size (int): Maximum tokens per window (default 1000).

    Returns:
        List[str]: List of chunked strings.
    """
    #TODO: Create an agent class for this and set default value for agent
    async def agent_get_split_points(text, agent) -> List[int]:
        results = await rt.call(agent, text)
        return results
    
    # Pre-chunk the text into small segments
    chunked_text = recursive_chunk_text(text, 200, 0)
    
    all_split_points = []
    current_chunk = 0
    last_chunk = 0
    window_text = []
    
    while current_chunk < len(chunked_text):
        # Build window starting from current_start_chunk
        char_count = 0
        
        for i in range(current_chunk, len(chunked_text)):
            #Add to the window
            window_text.append(f"<start_chunk_{i}>")
            window_text.append(chunked_text[i])
            window_text.append(f"<end_chunk_{i}>")

            #Update char count and index of last chunk added to window
            char_count += len(chunked_text[i])
            last_chunk = i
            if char_count > window_size:
                break
        
        # If we've reached the end, process everything remaining
        if last_chunk == len(chunked_text) - 1:
            split_points = asyncio.run(agent_get_split_points(window_text, agent))
            all_split_points.extend(split_points)
            break
        
        else:
            # Get split points for this window
            split_points = asyncio.run(agent_get_split_points(window_text, agent))
            
            if not split_points:
                # No splits suggested, move forward by 1 and try again
                current_chunk = last_chunk + 1
            
            else:
                # Only accept splits up to (but not including) the last one
                if len(split_points) > 1:
                    accepted_splits = split_points[:-1]
                    all_split_points.extend(accepted_splits)
                    # Start next window from the last (rejected) split point
                    current_chunk = split_points[-1]
                else:
                    # Only one split point so accept it and move just past it
                    all_split_points.extend(split_points)
                    current_chunk = split_points[-1] + 1
                
                window_text = []

    # Ensure we always include the end of the text as a split point to enclude whole text
    if len(chunked_text) not in all_split_points:
        all_split_points.append(len(chunked_text))
    
    # Now reconstruct the final chunks based on all split points
    chunks = []
    chunk = ""
    for i, text in enumerate(chunked_text):
        chunk += text
        if i in all_split_points:
            chunks.append(chunk)
            chunk = ""
    
    return chunks
    
#I need to finish up some embedding stuff before I can implement this
def kamradt_chunk(text: str, token_encoding : str, chunk_size : int = 200, threshold : float = 0.95) -> List[str]:
    """
    Chunks text using Kamradt's method (experimental, not fully implemented).

    Args:
        text (str): The text to chunk.
        token_encoding (str): Tokenizer encoding name.
        chunk_size (int): Target chunk size.
        threshold (float): Discontinuity threshold (unused).

    Returns:
        List[str]: List of chunked strings (currently returns empty string list).
    """
    def find_discontinuity(tokens : list) -> int:
        return 0
    rough_chunks = rough_chunk_text(text, token_encoding, chunk_size, 0, 0)
    tokenizer = tiktoken.get_encoding(token_encoding)
    tokenized_chunks = [tokenizer.encode(chunk) for chunk in rough_chunks]
    dq = deque(tokenized_chunks)

    return [""]


def cluster_chunk(content: str) -> List[str]:
    """
    Chunks content using clustering (not implemented).

    Args:
        content (str): The content to chunk.

    Returns:
        List[str]: List of chunked strings.
    """
    # TODO: Implement clustering-based chunking
    return []

#TODO: finish this function by implementing parent-child chunk class and returning list of them
def hierarchical_chunk_file(
    file_path: str,
    parent_chunk_size: int = 4000,
    chunk_size: int = 400,
    overlap: int = 200,
    delta: int = 100
) -> List[str]:
    """
    Hierarchically chunks a file into parent and child chunks.

    Args:
        file_path (str): Path to the file to chunk.
        parent_chunk_size (int): Size of parent chunks.
        chunk_size (int): Size of child chunks.
        overlap (int): Overlap between chunks.
        delta (int): Allowed deviation for boundary search.

    Returns:
        List[str]: List of chunked strings.
    """
    buffer = ""
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            buffer += line
            if len(buffer) >= parent_chunk_size:
                left_of, right_of = find_two_closest_occurrences(buffer, parent_chunk_size, delta)
                split_point = get_best_split_point(left_of, right_of, parent_chunk_size)
                parent_chunk = buffer[:split_point]
                buffer = buffer[split_point - overlap:]
                chunks = strict_chunk_text(parent_chunk, chunk_size=chunk_size, overlap=overlap)
    return chunks

#TODO: finish this function by implementing parent-child chunk class and returning list of them
def hierarchical_chunk_text(
    text: str,
    parent_chunk_size: int = 4000,
    chunk_size: int = 400,
    overlap: int = 200,
    delta: int = 100
) -> List[str]:
    """
    Hierarchically chunks text into parent and child chunks.

    Args:
        text (str): The text to chunk.
        parent_chunk_size (int): Size of parent chunks.
        chunk_size (int): Size of child chunks.
        overlap (int): Overlap between chunks.
        delta (int): Allowed deviation for boundary search.

    Returns:
        List[str]: List of chunked strings.
    """
    parent_chunks = recursive_chunk_text(text, parent_chunk_size, overlap)
    for parent_chunk in parent_chunks:
        chunks = strict_chunk_text(parent_chunk, chunk_size=chunk_size, overlap=overlap)
    return chunks

def find_two_closest_occurrences(
    text: str,
    index: int,
    delta: int,
    key: List[str] = [".", "?", "!"]
) -> tuple[int | None, int | None]:
    """
    Finds the closest occurrences of any key character to the left and right of index.

    Args:
        text (str): The text to search.
        index (int): The index to search around.
        delta (int): The range to search left and right.
        key (List[str], optional): Characters to search for.

    Returns:
        tuple[int | None, int | None]: Indices of closest left and right occurrences.
    """

    right_of = None
    left_of = None
    for i in range(index, min(index + delta + 1, len(text))):
        if text[i] in key:
            right_of = i + 1
            break
    for i in range(index, max(index - delta - 1, -1), -1):
        if text[i] in key:
            left_of = i + 1
            break

    return left_of, right_of

def get_best_split_point(
    left_of: int | None,
    right_of: int | None,
    index: int
) -> int:
    """
    Determines the best split point between left_of and right_of indices.

    Args:
        left_of (int | None): Index to the left.
        right_of (int | None): Index to the right.
        index (int): Target index.

    Returns:
        int: The best split point index.
    """
    if not right_of and not left_of:
        return index
    elif right_of is None:
        return left_of
    elif left_of is None:
        return right_of
    
    return left_of if index - left_of <= right_of - index else right_of


def estimate_chars_per_token(text: str, tokenizer: tiktoken.Encoding, sample_size: int = 1000) -> float:
    """
    Estimate average characters per token from a text sample.

    Args:
        text (str): The text to sample.
        tokenizer (tiktoken.Encoding): The tokenizer to use.
        sample_size (int): Number of characters to sample.

    Returns:
        float: Estimated characters per token.
    """
    sample = text[:min(len(text), sample_size)]
    tokens = len(tokenizer.encode(sample))
    return len(sample) / tokens if tokens > 0 else 4.0


def find_best_boundary(
    text: str,
    chunk_size: int,
    tokenizer: tiktoken.Encoding,
    search_delta: int,
    key: List[str] = [".", "?", "!"]
) -> int:
    """
    Find the best semantic boundary near target token count.

    Args:
        text (str): Full text to chunk.
        chunk_size (int): Target number of tokens for chunk.
        tokenizer (tiktoken.Encoding): Tokenizer to use.
        search_delta (int): Acceptable deviation from target_tokens.
        key (List[str]): Punctuation marks to split on.

    Returns:
        int: Position of best boundary.
    """
    # Estimate starting search position
    chars_per_token = estimate_chars_per_token(text, tokenizer)
    start_idx = int(chunk_size * chars_per_token)
    if start_idx >= len(text):
        return len(text)
    
    search_left = True
    search_right = True
    left_pos = start_idx
    right_pos = start_idx
    left_token_count = None
    right_token_count = None
    
    # Bidirectional search from estimated position
    while search_left or search_right:

        if search_right:
            #While we haven't found a key character, we're within delta, and were still within the string, keep searching right
            while text[right_pos] not in key and right_pos < start_idx + search_delta and right_pos < len(text) - 1:
                right_pos += 1
            
            token_count = len(tokenizer.encode(text[:right_pos]))
            if right_token_count is None:
                right_token_count = token_count

            # If new position is closer to target, update best
            if abs(token_count - chunk_size) < right_token_count:
                right_token_count = token_count

            #Check if we've gone over bound of what we can search
            if right_pos == len(text) - 1 or right_pos >= start_idx + search_delta:
                search_right = False

            #stop searching if we're at least as large as chunk size
            if token_count >= chunk_size:
                search_right = False
        
        if search_left:
            #While we haven't found a key character, we're within delta, and were still within the string, keep searching left
            while text[left_pos] not in key and start_idx - left_pos < search_delta and left_pos > 0:
                left_pos -= 1
            
            token_count = len(tokenizer.encode(text[:left_pos]))
            if left_token_count is None:
                left_token_count = token_count

            # If new position is closer to target, update best
            if abs(token_count - chunk_size) < left_token_count:
                left_token_count = token_count

            #Check if we've gone over bound of what we can search
            if left_pos == 0 or start_idx - left_pos <= search_delta:
                search_left = False

            #stop searching if we're at least as large as chunk size
            if token_count <= chunk_size:
                search_left = False
    
    return left_pos if abs(left_token_count - chunk_size) <= abs(right_token_count - chunk_size) else right_pos