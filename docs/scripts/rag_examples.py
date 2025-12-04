"""
RAG examples for use in documentation via --8<-- includes
"""


# --8<-- [start:simple_rag_example]
import asyncio
import railtracks as rt

def embedding_function(chunk: list[str]) -> list[list[float]]: ... # your embedding function here (Railtracks will be providing them soon [see issue #_]) 

vs = rt.vector_stores.ChromaVectorStore("My Vector Store", embedding_function)

Agent = rt.agent_node(
    "Simple Rag Agent",
    rag=rt.RagConfig(vector_store=vs, top_k=3),
    system_message="You are a helpful assistant",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)


question = "What does Steve like?"
response = asyncio.run(rt.call(Agent, question))

# --8<-- [end:simple_rag_example]

# --8<-- [start:rag_as_tool]
import railtracks as rt
from railtracks.llm import OpenAILLM

# 1) Build the retrieval node
vs = rt.vector_stores.ChromaVectorStore("My Vector Store", embedding_function=embedding_function)
@rt.function_node
def vector_query(query: str):
    return vs.search(query)


# 2) Create Agent and connect your vector query
agent = rt.agent_node(
    llm=OpenAILLM("gpt-4o"),
    tool_nodes=[vector_query],
)

# 3) Run the agent.
@rt.session()
async def main():
    question = "What is the work from home policy?"

    response = await rt.call(
        agent,
        user_input=(
            "Question:\n"
            f"{question}\n"
            "Answer based only on the context provided."
            "If the answer is not in the context, say \"I don't know\"."
        )
    )

    return response
# --8<-- [end:rag_as_tool]

# --8<-- [start:rag_with_files]
from railtracks.rag.utils import read_file

# Read file contents manually
try:
    doc1_content = read_file("./docs/faq.txt")
    doc2_content = read_file("./docs/policies.txt")
except FileNotFoundError:
    doc1_content = "FAQ file not found. Please ensure docs/faq.txt exists."
    doc2_content = "Policies file not found. Please ensure docs/policies.txt exists."


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

