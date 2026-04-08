from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pydantic import BaseModel

from .config import PIIEntity, PIIRedactConfig

_BUILTIN_PATTERNS: dict[PIIEntity, str] = {
    PIIEntity.EMAIL_ADDRESS: r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    PIIEntity.PHONE_NUMBER: (
        r"(?<![.\d/])"
        r"(?:\+\d{1,3}[\s\-.]?)?"
        r"(?:\(?\d{3}\)?[\s\-.]?)?"
        r"\d{3}[\s\-.]?\d{4}"
        r"(?!\d)"
        r"(?!\.\d)"
    ),
    PIIEntity.CREDIT_CARD: r"\b(?:\d[ \-]?){13,16}\b",
    PIIEntity.US_SSN: r"\b\d{3}-\d{2}-\d{4}\b",
    PIIEntity.CA_SIN: r"\b\d{3}-\d{3}-\d{3}\b",
    PIIEntity.IP_ADDRESS: r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    PIIEntity.URL: r"https?://[^\s<>\"']+",
    PIIEntity.IBAN_CODE: r"\b[A-Z]{2}\d{2}[\s]?[\dA-Z]{4}[\s]?(?:[\dA-Z]{4}[\s]?){1,7}[\dA-Z]{1,4}\b",
}

_PATTERN_PRIORITY: list[PIIEntity] = [
    PIIEntity.EMAIL_ADDRESS,
    PIIEntity.URL,
    PIIEntity.CREDIT_CARD,
    PIIEntity.IBAN_CODE,
    PIIEntity.US_SSN,
    PIIEntity.CA_SIN,
    PIIEntity.IP_ADDRESS,
    PIIEntity.PHONE_NUMBER,
]


_LUHN_VALIDATED: frozenset[str] = frozenset(
    {
        PIIEntity.CREDIT_CARD.value,
        PIIEntity.CA_SIN.value,
    }
)


def _passes_luhn(digits: str) -> bool:
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
    """A single redacted span (no raw value stored)."""

    entity_type: str
    placeholder: str
    start: int
    end: int


class _Span:
    """Internal mutable span used during detection before merging."""

    __slots__ = ("start", "end", "entity_type", "placeholder", "priority")

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
        for entity in _PATTERN_PRIORITY:
            if entity not in entity_set:
                continue
            raw = _BUILTIN_PATTERNS.get(entity)
            if raw is None:
                continue
            self._patterns.append((re.compile(raw), entity.value, f"[{entity.value}]"))
        for cp in config.custom_patterns:
            self._patterns.append((re.compile(cp.regex), cp.name, f"[{cp.name}]"))

    def redact(self, text: str) -> tuple[str, list[RedactionRecord]]:
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
    """Build the ``meta`` dict for ``GuardrailDecision``."""
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
