
import os
import asyncio
from typing import List

import pytest

import railtracks as rt
from railtracks.prebuilt import rag_node
from railtracks.rag.utils import read_file
from railtracks.llm import OpenAILLM
from railtracks.rag.rag_core import RAG, RAGConfig, SearchResult


pytestmark = pytest.mark.integration


def custom_rag_node(
    documents: List[str],
    embed_model: str = "text-embedding-3-small",
    token_count_model: str = "gpt-4o",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
):
    """Create a custom RAG node with specific configuration using the core RAG API."""
    rag_core = RAG(
        docs=documents,
        config=RAGConfig(
            embedding={"model": embed_model},
            store={},
            chunking={
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "model": token_count_model,
            },
        ),
    )
    rag_core.embed_all()

    def query(q: str, top_k: int = 1) -> SearchResult:
        return rag_core.search(q, top_k=top_k)

    return rt.function_node(query)


def test_simple_rag_example_e2e():
    retriever = rag_node(
        [
            "Steve likes apples and enjoys them as snacks",
            "John prefers bananas for their potassium content",
            "Alice loves oranges for vitamin C",
        ]
    )

    question = "What does Steve like?"
    results = asyncio.run(rt.call(retriever, question, top_k=3))

    context = "\n".join(
        f"Document {i+1} (score: {r.score:.4f}): {r.record.text}"
        for i, r in enumerate(results)
    )

    # Assertions: shape + relevance
    assert len(list(results)) == 3
    assert "Steve likes apples" in context
    # Contract checks for result entry and container
    first = list(results)[0]
    assert hasattr(first, "score") and isinstance(first.score, float)
    assert hasattr(first, "record") and hasattr(first.record, "text") and isinstance(first.record.text, str)
    assert hasattr(results, "to_list_of_texts")
    assert isinstance(results.to_list_of_texts(), list)


def test_rag_with_files_e2e(tmp_path, monkeypatch):
    # Prepare a docs directory with two files
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "faq.txt").write_text("FAQ: Common questions about working hours and tools.")
    (docs_dir / "policies.txt").write_text("Policies: Work from home allowed on Fridays.")

    # Use relative paths like users would
    monkeypatch.chdir(tmp_path)

    doc1_content = read_file("./docs/faq.txt")
    doc2_content = read_file("./docs/policies.txt")

    retriever = rag_node([doc1_content, doc2_content])

    question = "What is the work from home policy?"
    res = asyncio.run(rt.call(retriever, question, top_k=2))
    texts = res.to_list_of_texts()

    assert len(texts) == 2
    assert any("work from home" in t.lower() for t in texts)


def test_rag_topk_bounds_and_order_e2e():
    docs = [
        "Doc A: apples are red.",
        "Doc B: bananas are yellow.",
        "Doc C: oranges are orange.",
    ]
    retriever = rag_node(docs)

    # top_k larger than corpus should cap to the corpus size
    res_all = asyncio.run(rt.call(retriever, "What color are bananas?", top_k=10))
    assert len(list(res_all)) == len(docs)

    # top_k == 1 should return a single, relevant result
    res_one = asyncio.run(rt.call(retriever, "bananas", top_k=1))
    texts_one = res_one.to_list_of_texts()
    assert len(texts_one) == 1
    assert "bananas" in texts_one[0].lower()


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY to run")
def test_rag_with_llm_e2e():
    retriever = rag_node(
        [
            "Our company policy requires all employees to work from home on Fridays",
            "Data security guidelines mandate encryption of all sensitive customer information",
            "Employee handbook states vacation requests need 2 weeks advance notice",
        ]
    )

    question = "What is the work from home policy?"
    search_result = asyncio.run(rt.call(retriever, question, top_k=2))
    context = "\n\n".join(search_result.to_list_of_texts())

    agent = rt.agent_node(llm=OpenAILLM("gpt-4o"))

    with rt.Session(context={"context": context, "question": question}):
        response = asyncio.run(
            rt.call(
                agent,
                user_input=(
                    "Based on the following context, please answer the question.\n"
                    "Context:\n"
                    f"{context}\n"
                    "Question:\n"
                    f"{question}\n"
                    "Answer based only on the context provided. "
                    'If the answer is not in the context, say "I don\'t know".'
                ),
            )
        )

    assert hasattr(response, "content")
    assert isinstance(response.content, str)
    assert response.content.strip() != ""
    # Heuristic: answer should reference "Friday" or "work from home"
    lc = response.content.lower()
    assert "friday" in lc or "work from home" in lc


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY to run")
def test_custom_rag_node_build_and_query_e2e():
    retriever = custom_rag_node(
        [
            "Alpha team prefers morning meetings",
            "Beta team likes afternoon standsups",
            "Gamma team schedules evening retrospectives",
        ]
    )

    result = asyncio.run(rt.call(retriever, "When does Alpha team meet?", top_k=1))
    texts = result.to_list_of_texts()

    assert len(texts) == 1
    assert "alpha" in texts[0].lower()
    assert "morning" in texts[0].lower()


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY to run")
def test_custom_rag_topk_and_contract_e2e():
    docs = [
        "Doc A: The onboarding checklist includes security training and device setup.",
        "Doc B: PTO requests require a 2-week prior notice.",
        "Doc C: Work from home is allowed every Friday, subject to manager approval.",
        "Doc D: Standups happen every morning at 9 AM.",
    ]
    retriever = custom_rag_node(docs, chunk_size=400, chunk_overlap=100)

    res = asyncio.run(rt.call(retriever, "When is WFH allowed?", top_k=2))
    items = list(res)
    assert 1 <= len(items) <= 2

    texts = res.to_list_of_texts()
    assert any("work from home" in t.lower() or "wfh" in t.lower() for t in texts)

    # Contract checks
    first = items[0]
    assert hasattr(first, "score") and isinstance(first.score, float)
    assert hasattr(first, "record") and hasattr(first.record, "text") and isinstance(first.record.text, str)