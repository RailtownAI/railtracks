"""
RAG examples for use in documentation via --8<-- includes
"""

# --8<-- [start:simple_rag_example]
import railtracks as rt
from railtracks.prebuilt import rag_node

# Build the retrieval node with raw text documents
retriever = rag_node([
    "Steve likes apples and enjoys them as snacks",
    "John prefers bananas for their potassium content", 
    "Alice loves oranges for vitamin C"
])

# Retrieve relevant context
question = "Who likes apples?"
search_result = rt.call_sync(retriever, question, top_k=3)
context = "\n\n".join(search_result.to_list_of_texts())

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

# 2) Retrieve relevant context
question = "What is the work from home policy?"
search_result = rt.call_sync(retriever, question, top_k=2)
context = "\n\n".join(search_result.to_list_of_texts())

# 3) Create an agent that uses the retrieved context
@rt.agent_node
def policy_assistant(question: str, context: str) -> str:
    """Answer policy questions using retrieved context."""
    return f"""Based on the following context, please answer the question.

Context:
{context}

Question: {question}

Answer based only on the context provided. If the answer is not in the context, say "I don't know"."""

# 4) Create and configure the agent
agent = policy_assistant.bind(
    llm=OpenAILLM("gpt-4o"),
    tools=[]
)

# 5) Run the agent with context
# answer = rt.call_sync(agent, question=question, context=context)
# --8<-- [end:rag_with_llm]

# --8<-- [start:rag_with_files]
from railtracks.rag.utils import read_file

# Read file contents manually
doc1_content = read_file("./docs/faq.txt")
doc2_content = read_file("./docs/policies.txt")

# Build retriever with file contents
retriever = rag_node([
    doc1_content,
    doc2_content
])
# --8<-- [end:rag_with_files]

# --8<-- [start:custom_rag_node]
from typing import List
import railtracks as rt
from railtracks.rag.rag_core import RAG, SearchResult

def custom_rag_node(
    documents: List[str], 
    embed_model="text-embedding-3-small",
    token_count_model="gpt-4o",
    chunk_size=1000,
    chunk_overlap=200,
):
    """Create a custom RAG node with specific configuration."""
    
    rag_core = RAG(
        docs=documents,
        embed_config={"model": embed_model},
        store_config={},
        chunk_config={
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "model": token_count_model,
        },
    )
    rag_core.embed_all()

    def query(query: str, top_k: int = 1) -> SearchResult:
        return rag_core.search(query, top_k=top_k)

    return rt.function_node(query)
# --8<-- [end:custom_rag_node]

# --8<-- [start:custom_rag_usage]
# Usage of custom RAG node
retriever = custom_rag_node([
    "Alpha team prefers morning meetings", 
    "Beta team likes afternoon standsups",
    "Gamma team schedules evening retrospectives"
])

result = rt.call_sync(retriever, "When does Alpha team meet?", top_k=1)
texts = result.to_list_of_texts()
print(texts[0])  # Should contain information about Alpha team's morning meetings
# --8<-- [end:custom_rag_usage]
