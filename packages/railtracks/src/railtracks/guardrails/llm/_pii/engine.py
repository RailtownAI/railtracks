from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pydantic import BaseModel

from .config import PIIEntity, PIIRedactConfig

# Insertion order defines overlap precedence (earlier = wins in _merge_spans).
_BUILTIN_PATTERNS: dict[PIIEntity, str] = {
    PIIEntity.EMAIL_ADDRESS: r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    PIIEntity.URL: r"https?://[^\s<>\"']+",
    PIIEntity.CREDIT_CARD: r"\b(?:\d[ \-]?){13,16}\b",
    PIIEntity.IBAN_CODE: r"\b[A-Z]{2}\d{2}[\s]?[\dA-Z]{4}[\s]?(?:[\dA-Z]{4}[\s]?){1,7}[\dA-Z]{1,4}\b",
    PIIEntity.US_SSN: r"\b\d{3}-\d{2}-\d{4}\b",
    PIIEntity.CA_SIN: r"\b\d{3}-\d{3}-\d{3}\b",
    PIIEntity.IP_ADDRESS: r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    PIIEntity.PHONE_NUMBER: (
        r"(?<![.\d/])"
        r"(?:\+\d{1,3}[\s\-.]?)?"
        r"(?:\(?\d{3}\)?[\s\-.]?)?"
        r"\d{3}[\s\-.]?\d{4}"
        r"(?!\d)"
        r"(?!\.\d)"
    ),
}


_LUHN_VALIDATED: frozenset[str] = frozenset(
    {
        PIIEntity.CREDIT_CARD.value,
        PIIEntity.CA_SIN.value,
    }
)


def _passes_luhn(digits: str) -> bool:
    """Return whether ``digits`` satisfies the Luhn (mod 10) checksum.

    See: https://en.wikipedia.org/wiki/Luhn_algorithm

    Used to cut false positives on credit-card and Canadian SIN patterns.

    Args:
        digits: Only decimal digit characters (non-digits should be stripped by the
            caller).

    Returns:
        True if the Luhn check passes.
    """
    total = 0
    reverse = digits[::-1]
    for i, ch in enumerate(reverse):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


class RedactionRecord(BaseModel):
    """One redacted substring (placeholder only; original text is not stored).

    Attributes:
        entity_type: Detector label (built-in entity value or custom pattern name).
        placeholder: Replacement text inserted into the string (e.g. ``[EMAIL_ADDRESS]``).
        start: Start offset in the original string.
        end: End offset (exclusive) in the original string.
    """

    entity_type: str
    placeholder: str
    start: int
    end: int


class _Span:
    """Internal mutable span used during detection before merging."""

    def __init__(
        self, start: int, end: int, entity_type: str, placeholder: str, priority: int
    ):
        self.start = start
        self.end = end
        self.entity_type = entity_type
        self.placeholder = placeholder
        self.priority = priority


class PIIEngine:
    """
    Regex-based PII detection and redaction engine.

    Compile patterns once at construction time; call ``redact()`` for each text.
    """

    def __init__(self, config: PIIRedactConfig) -> None:
        self._patterns: list[tuple[re.Pattern[str], str, str]] = []
        entity_set = set(config.entities)
        for entity in _BUILTIN_PATTERNS:
            if entity not in entity_set:
                continue
            raw = _BUILTIN_PATTERNS[entity]
            self._patterns.append((re.compile(raw), entity.value, f"[{entity.value}]"))
        for cp in config.custom_patterns:
            self._patterns.append((re.compile(cp.regex), cp.name, f"[{cp.name}]"))

    def redact(self, text: str) -> tuple[str, list[RedactionRecord]]:
        """Replace detected spans with placeholders, merging overlaps by priority.

        Args:
            text: Input string to scan.

        Returns:
            The redacted string and a list of :class:`RedactionRecord` entries for
            each placeholder segment (offsets refer to ``text``).
        """
        spans = self._detect(text)
        if not spans:
            return text, []

        merged = _merge_spans(spans)
        records: list[RedactionRecord] = []
        parts: list[str] = []
        cursor = 0

        for span in merged:
            parts.append(text[cursor : span.start])
            parts.append(span.placeholder)
            records.append(
                RedactionRecord(
                    entity_type=span.entity_type,
                    placeholder=span.placeholder,
                    start=span.start,
                    end=span.end,
                )
            )
            cursor = span.end

        parts.append(text[cursor:])
        return "".join(parts), records

    def _detect(self, text: str) -> list[_Span]:
        spans: list[_Span] = []
        for priority, (pattern, entity_type, placeholder) in enumerate(self._patterns):
            for m in pattern.finditer(text):
                if entity_type in _LUHN_VALIDATED:
                    digits = re.sub(r"\D", "", m.group())
                    if not _passes_luhn(digits):
                        continue
                spans.append(
                    _Span(m.start(), m.end(), entity_type, placeholder, priority)
                )
        return spans


def _merge_spans(spans: list[_Span]) -> list[_Span]:
    """
    Sort by start offset, then by priority (lower = higher priority).
    When spans overlap, keep the higher-priority one; break ties by length.
    """
    spans.sort(key=lambda s: (s.start, s.priority))
    merged: list[_Span] = []
    for span in spans:
        if merged and span.start < merged[-1].end:
            prev = merged[-1]
            if span.priority < prev.priority:
                merged[-1] = span
            elif span.priority == prev.priority and (span.end - span.start) > (
                prev.end - prev.start
            ):
                merged[-1] = span
        else:
            merged.append(span)
    return merged


def build_redaction_meta(
    records: list[RedactionRecord], messages_affected: int | None = None
) -> dict[str, Any]:
    """Build the ``meta`` dict for :class:`~railtracks.guardrails.core.decision.GuardrailDecision`.

    Args:
        records: Redaction rows from :meth:`PIIEngine.redact`.
        messages_affected: For input guards, how many messages contained redactions.

    Returns:
        A dict with ``redacted_entities`` (counts per entity type) and optionally
        ``messages_affected``.
    """
    counts: Counter[str] = Counter()
    for r in records:
        counts[r.entity_type] += 1
    meta: dict[str, Any] = {
        "redacted_entities": [
            {"entity_type": et, "count": c} for et, c in counts.items()
        ],
    }
    if messages_affected is not None:
        meta["messages_affected"] = messages_affected
    return meta
