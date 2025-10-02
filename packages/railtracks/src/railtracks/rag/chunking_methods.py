from typing import List, Union
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

def strict_chunk(self, file_path : str | None = None, token_encoding : str = "cl100k_base", chunk_size : int = 400, overlap : int = 200, text: str | None = None) -> List[str]:
    chunks = []

    # The case in which you would like to chunk by tokens
    if token_encoding:
        tokenizer = LORAGTokenizer(token_encoding)
        buffer = []
        # Chunk a file if they specify a file path
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    tokens = tokenizer.encode(line)
                    buffer.append(tokens)
                    while len(buffer) >= chunk_size:
                        chunk = tokenizer.decode(buffer[:chunk_size])
                        chunks.append(chunk)
                        buffer = buffer[chunk_size - overlap:]
                if buffer:
                    chunks.append(tokenizer.decode(buffer))

        # Chunk a string if they specify text
        elif text:
            tokens = tokenizer.encode(text)
            buffer.append(tokens)
            while len(buffer) >= chunk_size:
                chunk = tokenizer.decode(buffer[:chunk_size])
                chunks.append(chunk)
                buffer = buffer[chunk_size - overlap:]
            if buffer:
                chunks.append(tokenizer.decode(buffer))

    #The case in which you would like to chunk by characters        
    else:
        buffer = ""
        # Chunk a file if they specify a file path
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    buffer += line
                    while len(buffer) >= chunk_size:
                        chunks.append(buffer[:chunk_size])
                        buffer = buffer[chunk_size - overlap:]
                if buffer:
                    chunks.append(buffer)

        # Chunk a string if they specify text
        elif text:
            buffer = text
            while len(buffer) >= chunk_size:
                chunks.append(buffer[:chunk_size])
                buffer = buffer[chunk_size - overlap:]
            if buffer:
                chunks.append(buffer)
                
    return chunks

def rough_chunk(self, content: str, token : bool = True, chunk_size : int = 400, overlap : int = 200) -> List[str]:
    pass

def recursive_chunk(self, content: str) -> List[str]:
    pass

def llm_chunk(self, content: str) -> List[str]:
    pass

def kamradt_chunk(self, content: str) -> List[str]:
    pass

def cluster_chunk(self, content: str) -> List[str]:
    pass

def hierarchical_chunk(self, content: str) -> List[str]:
    pass