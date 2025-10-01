"""
RAG examples for use in documentation via --8<-- includes
"""

# --8<-- [start:simple_rag_example]
import asyncio
import railtracks as rt
from railtracks.prebuilt import rag_node

retriever = rt.prebuilt.rag_node([
    "Steve likes apples and enjoys them as snacks",
    "John prefers bananas for their potassium content",
    "Alice loves oranges for vitamin C",
])

question = "What does Steve like?"
results = asyncio.run(rt.call(retriever, question, top_k=3))

context = "\n".join(
    f"Document {i+1} (score: {r.score:.4f}): {r.record.text}"
    for i, r in enumerate(results)
)

print(f"Question: {question}")
print(f"Retrieved context:\n{context}")
# --8<-- [end:simple_rag_example]

# --8<-- [start:rag_with_llm]
import railtracks as rt
from railtracks.prebuilt import rag_node
from railtracks.llm import OpenAILLM

# 1) Build the retrieval node
retriever = rag_node([
    "Our company policy requires all employees to work from home on Fridays",
    "Data security guidelines mandate encryption of all sensitive customer information",
    "Employee handbook states vacation requests need 2 weeks advance notice"
])

# 2) Create Agent
agent = rt.agent_node(
    llm=OpenAILLM("gpt-4o"),
)

# 3) Run the agent.
@rt.session()
async def main():
    question = "What is the work from home policy?"
    search_result = await rt.call(retriever, question, top_k=2)
    context = "\n\n".join(search_result.to_list_of_texts())
    
    response = await rt.call(
        agent,
        user_input=(
            "Based on the following context, please answer the question.\n"
            "Context:\n"
            f"{context}\n"
            "Question:\n"
            f"{question}\n"
            "Answer based only on the context provided."
            "If the answer is not in the context, say \"I don't know\"."
        )
    )
# --8<-- [end:rag_with_llm]

# --8<-- [start:rag_with_files]
from railtracks.rag.utils import read_file

# Read file contents manually
try:
    doc1_content = read_file("./docs/faq.txt")
    doc2_content = read_file("./docs/policies.txt")
except FileNotFoundError:
    doc1_content = "FAQ file not found. Please ensure docs/faq.txt exists."
    doc2_content = "Policies file not found. Please ensure docs/policies.txt exists."

# Build retriever with file contents
retriever = rag_node([
    doc1_content,
    doc2_content
])
# --8<-- [end:rag_with_files]

# --8<-- [start:custom_rag_node]
import railtracks as rt
from railtracks.rag.rag_core import RAG, RAGConfig, SearchResult

rag_core = RAG(
        docs=["<Your text here>", "..."],
        config=RAGConfig(
            embedding={"model": "text-embedding-3-small"},
            store={},
            chunking={
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "model": "gpt-4o",
            },
        )
    )
rag_core.embed_all()

@rt.function_node
async def custom_rag_node(query: str) -> SearchResult:
    """A custom RAG function node that retrieves documents based on a query."""
    return rag_core.search(query, top_k=5)
# --8<-- [end:custom_rag_node]

