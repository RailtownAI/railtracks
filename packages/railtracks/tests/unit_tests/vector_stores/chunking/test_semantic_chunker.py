import json
from unittest.mock import MagicMock, patch

import pytest

from railtracks.llm.message import AssistantMessage
from railtracks.llm.response import MessageInfo, Response
from railtracks.vector_stores import Chunk, SemanticChunker
from railtracks.vector_stores.chunking.semantic_chunker import _DEFAULT_PROMPT


def _make_response(text: str) -> Response:
    """Build a minimal Response whose message.content is *text*."""
    return Response(
        message=AssistantMessage(content=text),
        message_info=MessageInfo(),
    )


def _mock_llm(return_text: str):
    """Return a MagicMock LLM whose chat() returns *return_text*."""
    llm = MagicMock()
    llm.chat.return_value = _make_response(return_text)
    return llm


class TestSemanticChunkerInit:
    def test_default_prompt_assigned(self):
        llm = _mock_llm("[]")
        chunker = SemanticChunker(llm=llm)
        assert chunker._prompt == _DEFAULT_PROMPT

    def test_custom_prompt_assigned(self):
        llm = _mock_llm("[]")
        custom = "Split this: {text}"
        chunker = SemanticChunker(llm=llm, prompt=custom)
        assert chunker._prompt == custom

    def test_llm_stored(self):
        llm = _mock_llm("[]")
        chunker = SemanticChunker(llm=llm)
        assert chunker._llm is llm

    def test_inherits_base_chunker(self):
        from railtracks.vector_stores.chunking.base_chunker import BaseChunker
        chunker = SemanticChunker(llm=_mock_llm("[]"))
        assert isinstance(chunker, BaseChunker)


class TestSemanticChunkerSplitText:
    def test_empty_string_returns_empty_list(self):
        llm = _mock_llm("[]")
        chunker = SemanticChunker(llm=llm)
        result = chunker.split_text("")
        assert result == []
        llm.chat.assert_not_called()

    def test_returns_list_of_strings_from_llm(self):
        segments = ["First semantic segment.", "Second semantic segment."]
        llm = _mock_llm(json.dumps(segments))
        chunker = SemanticChunker(llm=llm)
        result = chunker.split_text("Some text")
        assert result == segments

    def test_llm_called_once_with_message_history(self):
        from railtracks.llm.history import MessageHistory

        llm = _mock_llm('["chunk"]')
        chunker = SemanticChunker(llm=llm)
        chunker.split_text("hello world")

        llm.chat.assert_called_once()
        args, _ = llm.chat.call_args
        assert isinstance(args[0], MessageHistory)
        assert len(args[0]) == 1

    def test_prompt_contains_text(self):
        llm = _mock_llm('["only chunk"]')
        chunker = SemanticChunker(llm=llm)
        chunker.split_text("my document text")

        args, _ = llm.chat.call_args
        message_content = args[0][0].content
        assert "my document text" in message_content

    def test_custom_prompt_used(self):
        llm = _mock_llm('["segment"]')
        chunker = SemanticChunker(llm=llm, prompt="Custom: {text}")
        chunker.split_text("doc")

        args, _ = llm.chat.call_args
        assert args[0][0].content == "Custom: doc"

    def test_strips_markdown_code_fence(self):
        raw = "```json\n[\"a\", \"b\"]\n```"
        llm = _mock_llm(raw)
        chunker = SemanticChunker(llm=llm)
        result = chunker.split_text("text")
        assert result == ["a", "b"]

    def test_strips_plain_code_fence(self):
        raw = "```\n[\"x\"]\n```"
        llm = _mock_llm(raw)
        chunker = SemanticChunker(llm=llm)
        result = chunker.split_text("text")
        assert result == ["x"]

    def test_raises_on_invalid_json(self):
        llm = _mock_llm("not json at all")
        chunker = SemanticChunker(llm=llm)
        with pytest.raises(ValueError, match="not valid JSON"):
            chunker.split_text("some text")

    def test_raises_when_llm_returns_json_object_not_array(self):
        llm = _mock_llm('{"chunk": "oops"}')
        chunker = SemanticChunker(llm=llm)
        with pytest.raises(ValueError, match="JSON array of strings"):
            chunker.split_text("some text")

    def test_raises_when_array_contains_non_strings(self):
        llm = _mock_llm('[1, 2, 3]')
        chunker = SemanticChunker(llm=llm)
        with pytest.raises(ValueError, match="JSON array of strings"):
            chunker.split_text("some text")

    def test_filters_out_empty_strings_in_response(self):
        llm = _mock_llm('["a", "", "b"]')
        chunker = SemanticChunker(llm=llm)
        result = chunker.split_text("text")
        assert result == ["a", "b"]


class TestSemanticChunkerChunk:
    def test_chunk_returns_chunk_objects(self):
        segments = ["Part one.", "Part two.", "Part three."]
        llm = _mock_llm(json.dumps(segments))
        chunker = SemanticChunker(llm=llm)
        chunks = chunker.chunk("Some document")
        assert all(isinstance(c, Chunk) for c in chunks)
        assert len(chunks) == 3

    def test_chunk_contents_match_llm_segments(self):
        segments = ["Alpha segment.", "Beta segment."]
        llm = _mock_llm(json.dumps(segments))
        chunker = SemanticChunker(llm=llm)
        chunks = chunker.chunk("text")
        assert [c.content for c in chunks] == segments

    def test_chunk_ids_are_auto_generated(self):
        segments = ["seg1", "seg2"]
        llm = _mock_llm(json.dumps(segments))
        chunker = SemanticChunker(llm=llm)
        chunks = chunker.chunk("text")
        assert all(c.id is not None for c in chunks)
        assert chunks[0].id != chunks[1].id

    def test_chunk_document_propagated(self):
        segments = ["part1", "part2"]
        llm = _mock_llm(json.dumps(segments))
        chunker = SemanticChunker(llm=llm)
        chunks = chunker.chunk("text", document="my-doc")
        assert all(c.document == "my-doc" for c in chunks)

    def test_chunk_metadata_propagated(self):
        segments = ["a", "b"]
        llm = _mock_llm(json.dumps(segments))
        chunker = SemanticChunker(llm=llm)
        meta = {"source": "test", "page": 1}
        chunks = chunker.chunk("text", metadata=meta)
        assert all(c.metadata == meta for c in chunks)

    def test_chunk_metadata_copied_per_chunk(self):
        segments = ["x", "y"]
        llm = _mock_llm(json.dumps(segments))
        chunker = SemanticChunker(llm=llm)
        meta = {"key": "original"}
        chunks = chunker.chunk("text", metadata=meta)
        chunks[0].metadata["key"] = "mutated"
        assert chunks[1].metadata["key"] == "original"
        assert meta["key"] == "original"

    def test_chunk_empty_text_returns_empty_list(self):
        llm = _mock_llm("[]")
        chunker = SemanticChunker(llm=llm)
        chunks = chunker.chunk("")
        assert chunks == []

    def test_chunk_single_segment(self):
        llm = _mock_llm('["The whole document is one chunk."]')
        chunker = SemanticChunker(llm=llm)
        chunks = chunker.chunk("The whole document is one chunk.")
        assert len(chunks) == 1
        assert chunks[0].content == "The whole document is one chunk."
