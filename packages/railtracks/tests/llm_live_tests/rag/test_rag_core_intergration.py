import pytest
from railtracks.rag import RAG, RAGConfig


@pytest.fixture(scope="module")
def set_docs(get_docs) -> RAG:
    docs = get_docs
    rag = RAG(
        docs,
        config=RAGConfig(
            embedding={"model": "text-embedding-3-small"},
            store={},
            chunking={
                "chunk_size": 100, "chunk_overlap": 20, "model": "gpt-4o",
            },
        )
    )

    rag.embed_all()
    return rag


def test_search_question(set_docs, get_docs):
    docs = get_docs
    rag: RAG = set_docs
    query = "What is the color of watermelon?"
    result = rag.search(query, top_k=2)
    print(query)
    print(result[0].record.text)
    print(result[1].record.text)
    assert isinstance(result, list)
    assert len(result) > 0
    # doc[2] should contain the watermelon description
    assert result[0].record.text == docs[2]


def test_search_confirmation(set_docs, get_docs):

    rag: RAG = set_docs
    docs = get_docs
    query = "Pear is yellow"
    result = rag.search(query, top_k=2)
    print(query)
    print(result[0].record.text)
    print(result[1].record.text)
    assert isinstance(result, list)
    assert len(result) > 0
    # doc[2] should contain the watermelon description
    assert result[0].record.text == docs[1]
