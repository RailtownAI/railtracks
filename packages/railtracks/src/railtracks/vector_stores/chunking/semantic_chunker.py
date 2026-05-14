"""LLM-based semantic chunking strategy.

Tradeoffs vs fixed-size chunking:
- Higher latency: one LLM call per document instead of a pure-Python split.
- Higher cost: input tokens ≈ document length; output tokens ≈ document length.
- Better retrieval quality: boundaries reflect meaning rather than character count,
  keeping related content (e.g. a question and its answer) in the same chunk.

Use this chunker for high-value documents where retrieval precision matters more
than throughput.
"""

import json
from typing import Any, Optional

from railtracks.llm.history import MessageHistory
from railtracks.llm.message import UserMessage
from railtracks.llm.model import ModelBase

from .base_chunker import BaseChunker

_DEFAULT_PROMPT = (
    "You are a document chunking assistant. Split the following text into semantically "
    "coherent segments. Each segment should contain a complete idea or topic. "
    "Return ONLY a JSON array of strings where each string is one chunk. "
    "Do not include any explanation, markdown, or extra text — just the raw JSON array.\n\n"
    "Text to chunk:\n{text}"
)


class SemanticChunker(BaseChunker):
    """Splits text by asking an LLM to identify natural semantic boundaries.

    Args:
        llm (ModelBase): LLM instance used to determine chunk boundaries.
        prompt (Optional[str]): Custom prompt template. Must contain ``{text}``
            as a placeholder for the document. Defaults to a built-in prompt.

    Note:
        ``chunk_size`` and ``overlap`` are inherited from ``BaseChunker`` but
        have no effect on the output — boundaries are determined by the LLM.
    """

    def __init__(
        self,
        llm: ModelBase,
        prompt: Optional[str] = None,
    ):
        super().__init__(chunk_size=400, overlap=0)
        self._llm = llm
        self._prompt = prompt if prompt is not None else _DEFAULT_PROMPT

    def split_text(self, text: str) -> list[str]:
        """Ask the LLM to split *text* into semantic chunks.

        Args:
            text (str): Raw text to chunk.

        Returns:
            list[str]: Semantic segments as determined by the LLM.

        Raises:
            ValueError: If the LLM response cannot be parsed as a JSON array
                of strings.
        """
        if not text:
            return []

        filled_prompt = self._prompt.format(text=text)
        history = MessageHistory([UserMessage(filled_prompt)])
        response = self._llm.chat(history)
        raw = str(response.message.content).strip()

        # Strip markdown code fences if the LLM wrapped the JSON in them.
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"SemanticChunker: LLM response is not valid JSON. "
                f"Got: {raw!r}"
            ) from exc

        if not isinstance(parsed, list) or not all(
            isinstance(item, str) for item in parsed
        ):
            raise ValueError(
                "SemanticChunker: LLM response must be a JSON array of strings. "
                f"Got: {parsed!r}"
            )

        return [chunk for chunk in parsed if chunk]
