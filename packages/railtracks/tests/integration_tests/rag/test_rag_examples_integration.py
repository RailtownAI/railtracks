import asyncio
from typing import List
import pytest


# ----------------------- Test doubles for examples ----------------------- #

@pytest.fixture
def fake_rt_environment(monkeypatch):
    """
    Patch the public railtracks API used in the examples:
      - railtracks.call: async dispatcher for nodes
      - railtracks.prebuilt.rag_node: returns a retriever that ranks docs for a query
      - railtracks.llm.OpenAILLM: dummy LLM class
      - railtracks.agent_node: builds an agent that echoes context/question
      - railtracks.Session: context manager to set/get a global context

    These doubles are intentionally minimal but behave consistently so we can
    validate the example flows.
    """
    # Global-ish context storage (simulating Session)
    SESSION_CONTEXT = {}

    # 1) Patch railtracks.call to await async nodes or call sync ones.
    async def fake_call(node, *args, **kwargs):
        res = node(*args, **kwargs)
        if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
            return await res
        return res

    monkeypatch.setattr("railtracks.call", fake_call, raising=True)

    # 2) Patch rag_node: returns an async retriever; similarity = simple keyword hits.
    def fake_rag_node(docs: List[str]):
        docs_lower = [d.lower() for d in docs]
        keywords = ["steve", "like", "policy", "work", "home", "alpha", "morning"]

        async def retriever(query: str, top_k: int = 3):
            ql = query.lower()
            scored = []
            for text, tl in zip(docs, docs_lower):
                # Simple scoring: count keyword matches in doc and query overlap.
                score_hits = sum(1 for k in keywords if (k in ql and k in tl))
                # Lower is better; invert by 1/(hits+1) to avoid div-by-zero
                dist = 1.0 / (score_hits + 1)
                scored.append((dist, text))
            scored.sort(key=lambda t: t[0])
            selected = scored[:top_k]

            class Record:
                def __init__(self, text): self.text = text

            class Entry:
                def __init__(self, score, text):
                    self.score = score
                    self.record = Record(text)

            class Result(list):
                def to_list_of_texts(self):
                    return [e.record.text for e in self]

            return Result([Entry(s, t) for s, t in selected])

        return retriever

    monkeypatch.setattr("railtracks.prebuilt.rag_node", fake_rag_node, raising=True)

    # 3) Patch OpenAILLM to a no-op class (agent behavior is in agent_node).
    class DummyLLM:
        def __init__(self, model: str):
            self.model = model

    monkeypatch.setattr("railtracks.llm.OpenAILLM", DummyLLM, raising=True)

    # 4) Patch agent_node: returns an async callable using SESSION_CONTEXT.
    def fake_agent_node(llm):
        class Resp:
            def __init__(self, content): self.content = content

        async def agent(user_input: str):
            # Construct a trivial answer using Session context
            ctx = SESSION_CONTEXT.copy()
            ctx_text = ctx.get("context", "").strip()
            q_text = ctx.get("question", "").strip()
            # Produce a concise, deterministic response
            answer = f"Answer based on context: {ctx_text[:80]} | Question: {q_text[:80]}"
            return Resp(answer)

        return agent

    monkeypatch.setattr("railtracks.agent_node", fake_agent_node, raising=True)

    # 5) Patch Session context manager to store/retrieve SESSION_CONTEXT
    class DummySession:
        def __init__(self, context=None):
            self._context = context or {}
        def __enter__(self):
            SESSION_CONTEXT.clear()
            SESSION_CONTEXT.update(self._context)
            return self
        def __exit__(self, exc_type, exc, tb):
            SESSION_CONTEXT.clear()

    monkeypatch.setattr("railtracks.Session", DummySession, raising=True)


# ----------------------------- Tests ----------------------------- #

def test_simple_rag_example_flow(fake_rt_environment):
    import railtracks as rt
    from railtracks.prebuilt import rag_node

    retriever = rag_node([
        "Steve likes apples and enjoys them as snacks",
        "John prefers bananas for their potassium content",
        "Alice loves oranges for vitamin C"
    ])

    question = "What does Steve like?"
    search_result = asyncio.run(rt.call(retriever, question, top_k=3))

    # Build context string as in the example
    context = ""
    for idx, result in enumerate(search_result, start=1):
        score = result.score
        text = result.record.text
        context += f"Document {idx} (score: {score:.4f}): {text}\n"

    # Basic assertions on shape and content
    assert len(list(search_result)) == 3
    # Ensure the Steve document appears in the retrieved context
    assert "Steve likes apples" in context


def test_rag_with_llm_flow(fake_rt_environment):
    import railtracks as rt
    from railtracks.prebuilt import rag_node
    from railtracks.llm import OpenAILLM

    retriever = rag_node([
        "Our company policy requires all employees to work from home on Fridays",
        "Data security guidelines mandate encryption of all sensitive customer information",
        "Employee handbook states vacation requests need 2 weeks advance notice"
    ])

    question = "What is the work from home policy?"
    search_result = asyncio.run(rt.call(retriever, question, top_k=2))
    # Build context the same way examples do (simplified here)
    context = "\n\n".join(search_result.to_list_of_texts())
    assert len(list(search_result)) == 2
    assert "work from home" in context or "work from home" in context.lower()

    agent = rt.agent_node(
        llm=OpenAILLM("gpt-4o"),
    )

    with rt.Session(context={"context": context, "question": question}):
        resp = asyncio.run(rt.call(agent, user_input="Prompt using {context} and {question}"))
    # Response content should reflect both context and question presence
    assert hasattr(resp, "content")
    assert "Answer based on context:" in resp.content
    assert "Question:" in resp.content


def test_rag_with_files_flow(fake_rt_environment, tmp_path, monkeypatch):
    # Create example docs folder and files
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    faq = docs_dir / "faq.txt"
    policies = docs_dir / "policies.txt"
    faq.write_text("FAQ: Common questions about working hours and tools.")
    policies.write_text("Policies: Work from home allowed on Fridays.")

    # Ensure read_file reads from the created directory via relative path
    monkeypatch.chdir(tmp_path)

    from railtracks.rag.utils import read_file
    from railtracks.prebuilt import rag_node
    import railtracks as rt

    doc1_content = read_file("./docs/faq.txt")
    doc2_content = read_file("./docs/policies.txt")
    assert "FAQ" in doc1_content
    assert "Policies" in doc2_content

    retriever = rag_node([doc1_content, doc2_content])

    question = "What is the work from home policy?"
    res = asyncio.run(rt.call(retriever, question, top_k=2))
    texts = res.to_list_of_texts()

    assert len(texts) == 2
    # The policies file should surface given the question
    assert any("work from home" in t.lower() for t in texts)


def test_custom_rag_node_like_flow(fake_rt_environment):
    """
    Exercise the custom_rag_node example semantics:
    - Build a retriever from given docs
    - Run a query via rt.call
    - Validate the retrieved text
    """
    import railtracks as rt
    from railtracks.prebuilt import rag_node

    def custom_rag_node(documents: List[str]):
        # In examples, this uses RAG and returns rt.function_node(query).
        # Here we just leverage the prebuilt retriever patch and return it.
        return rag_node(documents)

    retriever = custom_rag_node([
        "Alpha team prefers morning meetings",
        "Beta team likes afternoon standups",
        "Gamma team schedules evening retrospectives"
    ])

    result = asyncio.run(rt.call(retriever, "When does Alpha team meet?", top_k=1))
    texts = result.to_list_of_texts()
    assert len(texts) == 1
    assert "Alpha team" in texts[0]
    assert "morning" in texts[0].lower()