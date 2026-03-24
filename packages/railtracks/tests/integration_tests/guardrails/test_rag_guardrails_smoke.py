"""
Minimal RAG + guardrails smoke test.

NOTE: RAG retrieval quality, chunking, and interaction with guardrails (ordering,
false positives, and injection shape) are not thoroughly validated here. This test
only checks that `agent_node(..., rag=..., guardrails=...)` runs without error and
invokes the mock LLM. Further investigation of RAG + guardrails is recommended
before relying on this combination in production.
"""

from __future__ import annotations

from typing import Any

import pytest
import railtracks as rt
from pydantic import BaseModel, Field

from railtracks.built_nodes.concrete.rag import RagConfig
from railtracks.guardrails import Guard, GuardrailDecision
from railtracks.vector_stores.vector_store_base import (
    FetchResponse,
    OneOrMany,
    SearchResponse,
    VectorStore,
)


class _EmptySearchVectorStore(VectorStore):
    """Minimal store: `search` returns no hits (RAG path still runs)."""

    def upsert(self, content: OneOrMany[Any]) -> OneOrMany[str]:
        raise NotImplementedError()

    def fetch(self, ids: OneOrMany[str]) -> FetchResponse:
        return []

    def search(
        self,
        query: OneOrMany[Any],
        top_k: int = 10,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> OneOrMany[SearchResponse]:
        if isinstance(query, list):
            return [[] for _ in query]
        return []

    def delete(self, ids: OneOrMany[str], where: dict[str, Any] | None = None) -> None:
        return None

    def count(self) -> int:
        return 0


class _RagAnswer(BaseModel):
    text: str = Field(default="rag")


@pytest.mark.asyncio
async def test_rag_plus_guardrails_minimal_smoke(mock_llm):
    def allow(_e) -> GuardrailDecision:  # type: ignore[no-untyped-def]
        return GuardrailDecision.allow()

    llm = mock_llm(custom_response='{"text":"ok"}')
    counts = {"n": 0}
    real = llm._structured

    def wrapped(messages, schema, **kwargs):  # type: ignore[no-untyped-def]
        counts["n"] += 1
        return real(messages, schema, **kwargs)

    llm._structured = wrapped  # type: ignore[method-assign]

    vs = _EmptySearchVectorStore("rag-test", lambda texts: [[0.0] for _ in texts])

    Agent = rt.agent_node(
        name="rag-guarded",
        output_schema=_RagAnswer,
        llm=llm,
        rag=RagConfig(vector_store=vs, top_k=1),
        guardrails=Guard(input=[allow]),
    )

    with rt.Session():
        await rt.call(Agent, user_input="question")

    assert counts["n"] == 1
