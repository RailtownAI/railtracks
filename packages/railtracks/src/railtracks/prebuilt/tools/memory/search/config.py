from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LexicalSearchConfig:
    """Tunable scoring weights for :class:`~.lexical.LexicalSearch`.

    Defaults are tuned so an exact key match dominates, a key hit outranks a
    value hit, and multi-term queries reward broader coverage; see the field
    docs below. Override individual fields to bias ranking for a specific
    corpus, e.g. raise ``value_coverage`` when values are long free-text notes
    rather than short facts, or lower ``fuzzy_threshold`` to be more forgiving
    of typos at the cost of more false positives.
    """

    # Phrase-level: the whole query as a substring. An exact key is the
    # jackpot; a key substring still outranks a value substring.
    exact_key: float = 100.0
    key_substring: float = 25.0
    value_substring: float = 10.0

    # Token-level: coverage of the query terms in each field, scaled by the
    # fraction of query tokens matched. Key hits outrank value hits.
    key_coverage: float = 8.0
    value_coverage: float = 4.0

    # A query token with no exact match in a field still counts, scaled by
    # its similarity, when the closest token in that field clears this
    # threshold (0.0-1.0). Higher = stricter (fewer, more confident matches).
    fuzzy_threshold: float = 0.8
