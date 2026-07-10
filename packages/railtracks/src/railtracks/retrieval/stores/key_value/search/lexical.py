from __future__ import annotations

import re
from difflib import SequenceMatcher

from .config import LexicalSearchConfig

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Split ``text`` into lowercase alphanumeric tokens."""
    return _TOKEN_RE.findall(text.casefold())


class LexicalSearch:
    """Weighted token-overlap ranking over key-value pairs.

    A pure, stateless algorithm — no embeddings, no I/O, no dependency on any
    concrete store. It ranks the ``{key: value}`` snapshot a caller already
    holds (typically ``KeyValueStore.items()``). Satisfies
    :class:`~.protocol.SearchAlgorithm`.

    Scoring combines a phrase-level pass (does the whole query appear as a
    substring of the key or value?) with token-level coverage of both fields.
    The *key* is treated as a deliberate handle rather than just more text, so
    a hit there outranks a hit in a value, and an exact key match is the top
    signal. A per-token fuzzy fallback (stdlib :class:`difflib.SequenceMatcher`)
    catches typos and morphological variants (``hiking`` vs ``hikes``) without
    pulling in a new dependency. All weights and the fuzzy threshold are
    tunable via :class:`~.config.LexicalSearchConfig`.

    Intended for small stores (an agent's memory holds tens to low hundreds of
    entries); the fuzzy fallback is O(entries x query_tokens x field_tokens),
    which is inconsequential at that scale.
    """

    def __init__(self, config: LexicalSearchConfig | None = None) -> None:
        self._config = config if config is not None else LexicalSearchConfig()

    def _coverage(self, query_tokens: list[str], field_tokens: list[str]) -> float:
        """Fraction of ``query_tokens`` found in ``field_tokens`` (0.0 - 1.0).

        An exact token match contributes 1.0. A token with no exact match
        contributes its best fuzzy similarity to any field token, but only
        when that similarity clears ``fuzzy_threshold`` — otherwise it
        contributes 0.0.
        """
        if not query_tokens or not field_tokens:
            return 0.0
        field_set = set(field_tokens)
        total = 0.0
        for qt in query_tokens:
            if qt in field_set:
                total += 1.0
                continue
            best = max(
                (SequenceMatcher(None, qt, ft).ratio() for ft in field_set),
                default=0.0,
            )
            if best >= self._config.fuzzy_threshold:
                total += best
        return total / len(query_tokens)

    def search(
        self, items: dict[str, str], query: str, *, top_k: int = 5
    ) -> list[tuple[str, str, float]]:
        cfg = self._config
        q = query.strip()
        if not q:
            return []
        q_cf = q.casefold()
        query_tokens = _tokenize(q)

        scored: list[tuple[str, str, float]] = []
        for key, value in items.items():
            key_cf = key.casefold()
            value_cf = value.casefold()
            score = 0.0

            # Phrase-level: the whole query as a substring. Exact key is the
            # jackpot; a key substring still outranks a value substring.
            if q_cf == key_cf:
                score += cfg.exact_key
            elif q_cf in key_cf:
                score += cfg.key_substring
            if q_cf in value_cf:
                score += cfg.value_substring

            # Token-level: coverage of the query terms in each field.
            score += cfg.key_coverage * self._coverage(query_tokens, _tokenize(key))
            score += cfg.value_coverage * self._coverage(
                query_tokens, _tokenize(value)
            )

            if score > 0.0:
                scored.append((key, value, score))

        scored.sort(key=lambda entry: entry[2], reverse=True)
        return scored[:top_k]
