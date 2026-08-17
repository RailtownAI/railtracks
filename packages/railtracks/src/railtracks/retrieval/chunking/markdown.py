"""Markdown-header-aware chunker.

Splits a Markdown document along heading boundaries and preserves
heading context on each chunk:

* ``metadata["headers"]`` — ordered list of ancestor headings for the
  chunk (e.g. ``["# Intro", "## Background"]``).
* ``metadata["section"]`` — the immediate heading the chunk belongs to,
  or ``None`` for pre-heading preamble.

When ``chunk_size`` is set and a section's body exceeds it (measured via
``length_fn``), the section body is delegated to a fallback
:class:`Splitter` (default: :class:`RecursiveSplitter`). Each sub-piece
becomes its own chunk, sharing the same header breadcrumb.
"""

from __future__ import annotations

import re
from typing import Callable

from ..models import Chunk, Document
from .base import Chunker, Splitter
from .recursive import RecursiveSplitter

_DEFAULT_HEADERS: list[str] = ["#", "##", "###"]


class MarkdownHeaderChunker(Chunker):
    """Chunks along Markdown headings, preserving heading context.

    Args:
        headers_to_split_on: Heading prefixes to treat as section
            boundaries (e.g. ``["#", "##", "###"]``). Any heading level
            not listed is treated as body text.
        chunk_size: Optional cap on per-chunk size (measured via
            ``length_fn``). When a section body exceeds this cap, the
            body is delegated to ``fallback_splitter``. When ``None``,
            section bodies are never subdivided.
        fallback_splitter: Splitter to use for overflowing section
            bodies. Defaults to a :class:`RecursiveSplitter` sized at
            ``chunk_size`` (when provided).
        length_fn: Length measure; defaults to :func:`len`.
    """

    def __init__(
        self,
        headers_to_split_on: list[str] | None = None,
        chunk_size: int | None = None,
        fallback_splitter: Splitter | None = None,
        length_fn: Callable[[str], int] | None = None,
    ) -> None:
        if chunk_size is not None and chunk_size <= 0:
            raise ValueError("'chunk_size' must be greater than 0 when provided")

        headers = (
            list(headers_to_split_on)
            if headers_to_split_on is not None
            else list(_DEFAULT_HEADERS)
        )
        for h in headers:
            if not h or set(h) != {"#"}:
                raise ValueError(
                    f"header specifiers must be strings of '#' characters, got {h!r}"
                )
        # Sort by length descending so '##' is matched before '#'.
        self.headers_to_split_on = sorted(headers, key=len, reverse=True)
        self.max_header_level = max(len(h) for h in self.headers_to_split_on)

        self.chunk_size = chunk_size
        self.length_fn: Callable[[str], int] = length_fn or len

        if fallback_splitter is not None:
            self.fallback_splitter: Splitter | None = fallback_splitter
        elif chunk_size is not None:
            self.fallback_splitter = RecursiveSplitter(
                chunk_size=chunk_size,
                overlap=0,
                length_fn=self.length_fn,
            )
        else:
            self.fallback_splitter = None

    def chunk(self, document: Document) -> list[Chunk]:
        text = document.content
        if not text:
            return []

        sections = self._split_into_sections(text)
        if not sections:
            return []

        pieces: list[str] = []
        offsets: list[tuple[int, int]] = []
        extra_metadata: list[dict] = []

        for section in sections:
            body = section["body"]
            body_start = section["body_start"]
            body_end = section["body_end"]
            headers = section["headers"]
            immediate = headers[-1] if headers else None
            meta_base = {"headers": list(headers), "section": immediate}

            if not body.strip():
                continue

            if (
                self.chunk_size is None
                or self.fallback_splitter is None
                or self.length_fn(body) <= self.chunk_size
            ):
                pieces.append(body)
                offsets.append((body_start, body_end))
                extra_metadata.append(dict(meta_base))
                continue

            # Delegate oversized bodies to the fallback splitter.
            sub_pieces_with_offsets = self._fallback_with_offsets(body, body_start)
            for sub, s, e in sub_pieces_with_offsets:
                pieces.append(sub)
                offsets.append((s, e))
                extra_metadata.append(dict(meta_base))

        return self._make_chunks(
            document, pieces, offsets=offsets, extra_metadata=extra_metadata
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _split_into_sections(self, text: str) -> list[dict]:
        """Walk the text line by line and emit one section per heading run.

        Each returned entry has:
            - ``headers``: ordered list of ancestor heading strings
              (e.g. ``["# Intro", "## Background"]``)
            - ``body``: the body text under the deepest heading (may
              include content up to the next heading of equal or
              shallower level)
            - ``body_start``, ``body_end``: absolute character offsets
              of ``body`` into ``text``.
        """
        header_re = re.compile(r"^(#{1,%d})\s+(.*)$" % self.max_header_level)

        # First sweep: identify header lines and their absolute offsets.
        # We need absolute offsets, so walk the text manually.
        sections: list[dict] = []
        heading_stack: list[tuple[int, str]] = []  # (level, full_line "# Title")

        # Split into lines with positions.
        line_entries: list[
            tuple[str, int, int]
        ] = []  # (line_text_without_newline, start, end_including_newline)
        cursor = 0
        for line in text.splitlines(keepends=True):
            stripped = line.rstrip("\n\r")
            line_entries.append((stripped, cursor, cursor + len(line)))
            cursor += len(line)

        # We emit one section per "run" between heading lines. Pre-heading
        # content becomes a section with an empty heading stack.
        current_body_start: int | None = None
        current_body_end: int | None = None
        current_headers: list[str] = list(heading_stack_as_strings(heading_stack))

        def flush(body_end: int) -> None:
            nonlocal current_body_start, current_body_end
            if current_body_start is None:
                return
            raw_body = text[current_body_start:body_end]
            stripped = raw_body.strip()
            if stripped:
                # Tighten offsets to the stripped body so that
                # doc.content[body_start:body_end] == stripped.
                leading = len(raw_body) - len(raw_body.lstrip())
                trailing = len(raw_body) - len(raw_body.rstrip())
                tight_start = current_body_start + leading
                tight_end = body_end - trailing
                sections.append(
                    {
                        "headers": list(current_headers),
                        "body": stripped,
                        "body_start": tight_start,
                        "body_end": tight_end,
                    }
                )
            current_body_start = None
            current_body_end = None

        for line_text, line_start, line_end in line_entries:
            m = header_re.match(line_text)
            if m and ("#" * len(m.group(1))) in self.headers_to_split_on:
                flush(line_start)
                level = len(m.group(1))
                # Pop headings at equal or deeper level.
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, line_text.strip()))
                current_headers = heading_stack_as_strings(heading_stack)
                current_body_start = line_end
                current_body_end = line_end
                continue

            if current_body_start is None:
                current_body_start = line_start
            current_body_end = line_end

        if current_body_start is not None:
            flush(current_body_end if current_body_end is not None else len(text))

        # Strip sections whose body is entirely empty/whitespace.
        return [s for s in sections if s["body"].strip() or s["headers"]]

    def _fallback_with_offsets(
        self, body: str, base_offset: int
    ) -> list[tuple[str, int, int]]:
        """Run the configured fallback splitter on ``body`` and recover offsets.

        When the fallback is a :class:`RecursiveSplitter`, we use its
        offset-aware ``split_with_positions`` directly. Otherwise, we
        fall back to ``str.find`` to locate each piece inside ``body``.
        """
        splitter = self.fallback_splitter
        assert splitter is not None  # guaranteed by caller

        if isinstance(splitter, RecursiveSplitter):
            return [
                (piece, base_offset + s, base_offset + e)
                for piece, s, e in splitter.split_with_positions(body)
            ]

        out: list[tuple[str, int, int]] = []
        cursor = 0
        for piece in splitter.split(body):
            if not piece:
                continue
            idx = body.find(piece, cursor)
            if idx < 0:
                idx = body.find(piece)
            if idx < 0:
                idx = cursor
            end = idx + len(piece)
            out.append((piece, base_offset + idx, base_offset + end))
            cursor = end
        return out


def heading_stack_as_strings(stack: list[tuple[int, str]]) -> list[str]:
    return [s for _, s in stack]
