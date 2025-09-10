"""
Text processing module for LORAG.

This module provides functionality for processing text, including chunking and summarization.
"""

from logging import getLogger
from typing import Any, Callable, List, Optional

from .utils import Tokenizer

logger = getLogger(__name__)


class BaseChunkingService:
    """
    Base class for media chunking services.

    Args:
        chunk_size (int): Size of each chunk in bytes/tokens/characters.
        chunk_overlap (int): Overlap between chunks.
        strategy (Optional[Callable]): Callable for the chunking strategy.
    """

    def __init__(
        self,
        chunk_size: int = 2048,
        chunk_overlap: int = 256,
        strategy: Optional[Callable] = None,
        *other_configs,
        **other_kwargs,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.other_configs = other_configs
        self.other_kwargs = other_kwargs
        # Assign strategy and bind if needed
        if strategy is not None:
            # If it's an unbound method (e.g., Class.method), bind to self
            if hasattr(strategy, "__self__") and strategy.__self__ is not None:
                # Already bound method (self.method)
                self.strategy = strategy
            else:
                # Function or unbound method (e.g., Class.method)
                self.strategy = strategy.__get__(self)
        else:
            self.strategy = None  # Must be set in subclass, or on instance

    def chunk(self, content: Any, *args, **kwargs):
        """
        Invoke the assigned chunking strategy on content.

        Args:
            content: The media/text to chunk.
            *args, **kwargs: Passed to the chunking strategy.
        Returns:
            Chunked content as per the strategy.
        """
        if not callable(self.strategy):
            raise ValueError("No chunking strategy set or strategy is not callable.")
        return self.strategy(content, *args, **kwargs)

    def set_strategy(self, new_strategy: Callable):
        """
        Set a new chunking strategy, binding it if needed.
        """
        if not callable(new_strategy):
            raise ValueError("Strategy must be callable.")
        # If unbound, bind to self
        if hasattr(new_strategy, "__self__") and new_strategy.__self__ is not None:
            self.strategy = new_strategy
        else:
            self.strategy = new_strategy.__get__(self)

    def chunk_file(self, file_path: str) -> List[Any]:
        """
        Split file into chunks based on strategy.
        """
        raise NotImplementedError("Subclasses must implement this method.")


class TextChunkingService(BaseChunkingService):
    """Processor for text operations."""

    strategies = ["chunk_by_char", "chunk_by_token", "chunk_smart"]

    def __init__(
        self,
        chunk_size: int = 2048,
        chunk_overlap: int = 256,
        model: Optional[str] = "gpt-3.5-turbo",
        strategy: Optional[Callable] = None,
        *other_configs,
        **other_kwargs,
    ):
        """
        Initialize the text chunker.

        Args:
            chunk_size: Size of each chunk in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.model = model
        super().__init__(
            chunk_size, chunk_overlap, strategy, *other_configs, **other_kwargs
        )

    def chunk_by_char(
        self,
        content: str,
    ) -> List[str]:
        """
        Split text into chunks
        """
        chunks = []
        start = 0

        # end was used but never declared in the original code snippet;
        # we'll add a separate approach or define end before the loop.
        while start < len(content):
            end = min(start + self.chunk_size, len(content))
            chunk = content[start:end]
            chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap

        return chunks

    def chunk_by_token(self, content: str) -> List[str]:
        """
        Split text into chunks by token.

        TODO: use LLM to do this
        """
        chunks = []
        if not self.model:
            error_message = "Model not specified for token chunking."
            logger.error(error_message)
            raise ValueError(error_message)
        tokenizer = Tokenizer(self.model)
        tokens = tokenizer.encode(content)

        if self.chunk_overlap > self.chunk_size:
            logger.warning(
                f"Warning: chunk_overlap ({self.chunk_overlap}) is greater than chunk_size ({self.chunk_size})."
                " Should be <= 40%"
            )
            raise ValueError("chunk_overlap should be less than or equal to chunk_size")

        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            token_chunk = tokens[start:end]
            chunk = tokenizer.decode(token_chunk)

            chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap
            if end >= len(tokens):
                break

        return chunks
