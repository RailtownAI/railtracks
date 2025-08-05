import pytest
import railtracks as rt

from railtracks.nodes.nodes import Node
from railtracks.prebuilt import rag_node





def test_node_search_question(get_docs):

    docs = get_docs
    node = rag_node(
        documents=docs,
    )

    query = "What is the color of watermelon?"
    result = rt.call_sync(node, query)
    print(query)
    print(result[0].record.text)
    print(result[1].record.text)
    assert isinstance(result, list)
    assert len(result) > 0
    # doc[2] should contain the watermelon description
    assert result[0].record.text == docs[2]


def test_node_search_confirmation(get_docs):
    docs = get_docs
    node = rag_node(
        documents=docs,
    )

    query = "Pear is yellow"
    result = rt.call_sync(node, query)
    print(query)
    print(result[0].record.text)
    print(result[1].record.text)
    assert isinstance(result, list)
    assert len(result) > 0
    # doc[2] should contain the watermelon description
    assert result[0].record.text == docs[1]
