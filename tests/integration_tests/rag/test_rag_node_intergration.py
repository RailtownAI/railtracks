import pytest
import railtracks as rt
from railtracks.RAG.rag_node import get_rag_node
from conftest import get_docs

def test_node_search_question(get_docs):
    docs = get_docs
    rag_node: rt.Node = get_rag_node(
        documents=docs,
    )

    query = "What is the color of watermelon?"
    result = rt.call_sync(rag_node, query)
    print(query)
    print(result[0].record.text)
    print(result[1].record.text)
    assert isinstance(result, list)
    assert len(result) > 0
    # doc[2] should contain the watermelon description
    assert result[0].record.text == docs[2]


def test_node_search_confirmation(get_docs):
    docs = get_docs
    rag_node: rt.Node = get_rag_node(
        documents=docs,
    )

    query = "Pear is yellow"
    result = rt.call_sync(rag_node, query)
    print(query)
    print(result[0].record.text)
    print(result[1].record.text)
    assert isinstance(result, list)
    assert len(result) > 0
    # doc[2] should contain the watermelon description
    assert result[0].record.text == docs[1]
