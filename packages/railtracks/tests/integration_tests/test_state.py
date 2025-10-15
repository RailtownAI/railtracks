import json
import random
import time
from collections import Counter
from typing import List, TypeVar

import pytest
import railtracks as rt
from jsonschema import ValidationError, validate
from railtracks.llm.response import MessageInfo, Response
from railtracks.nodes.nodes import Node
from railtracks.state.forest import AbstractLinkedObject
from railtracks.state.node import LinkedNode
from railtracks.state.request import RequestTemplate
from railtracks.state.utils import create_sub_state_info
from railtracks.utils.profiling import Stamp


def generate_ids():
    return RequestTemplate.generate_id()


def create_linked_request(identifier, source, sink):
    return RequestTemplate(
        identifier,
        source_id=source,
        sink_id=sink,
        parent=None,
        input=((), {}),
        output=None,
        stamp=Stamp(identifier="test", time=time.time(), step=1),
    )


def create_node():
    return rt.function_node(random.random).node_type()


def create_linked_node(node: Node):
    return LinkedNode(
        identifier=node.uuid,
        _node=node,
        parent=None,
        stamp=Stamp(identifier="test", time=time.time(), step=1),
    )


T = TypeVar("T", bound=AbstractLinkedObject)


def to_heap(items: List[T]):
    return {item.identifier: item for item in items}


@pytest.fixture
def request_structure():
    # Graph 1:
    #
    nodes = [create_node() for _ in range(7)]
    ids = [n.uuid for n in nodes]

    r_ids = [f"{i}" for i in range(7)]

    requests = [
        create_linked_request(r_ids[0], None, ids[0]),
        create_linked_request(r_ids[1], ids[0], ids[1]),
        create_linked_request(r_ids[2], ids[0], ids[2]),
        create_linked_request(r_ids[3], ids[1], ids[3]),
        create_linked_request(r_ids[4], None, ids[4]),
        create_linked_request(r_ids[5], ids[4], ids[5]),
        create_linked_request(r_ids[6], ids[4], ids[6]),
    ]

    linked_nodes = [create_linked_node(n) for n in nodes]

    return to_heap(linked_nodes), to_heap(requests), ids, r_ids


def test_one_piece(request_structure):
    node_heap = request_structure[0]
    request_heap = request_structure[1]
    ids = request_structure[2]
    r_ids = request_structure[3]

    node_forest, request_forest = create_sub_state_info(
        node_heap, request_heap, r_ids[0]
    )

    assert len(node_forest.heap()) == 4
    assert len(request_forest.heap()) == 4
    sinks = [r.sink_id for r in request_forest.heap().values()]
    sources = [r.source_id for r in request_forest.heap().values()]
    for s in sinks:
        assert s in node_forest.heap().keys(), f"Sink {s} not found in node forest"
    assert None in sources, "There should be a source with None ID"
    for s in sources:
        if s is None:
            continue
        assert s in node_forest.heap(), f"Source {s} not found in node forest"

    assert Counter(sinks) == Counter([ids[0], ids[1], ids[2], ids[3]])
    assert Counter(sources) == Counter([None, ids[0], ids[1], ids[0]])


def test_no_changes(request_structure):
    node_heap, request_heap, ids, r_ids = request_structure

    node_forest, request_forest = create_sub_state_info(
        node_heap, request_heap, [r_ids[0], r_ids[4]]
    )

    assert node_forest.heap() == node_heap, (
        "There should be no changes because the filter doesn't change things"
    )
    assert request_forest.heap() == request_heap, (
        "There should be no changes because the filter doesn't change things"
    )


async def test_json_serialization(planner_node, json_state_schema):
    with rt.Session(logging_setting="NONE") as session:
        await rt.call(planner_node, "New York", "Houston")

    try:
        validate(session.payload(), json_state_schema)
    except ValidationError:
        raise


async def test_json_serialization_2(planner_with_llm_node, json_state_schema, mock_llm):
    # ============ mock llm config =========
    def random_number(messages):
        if rt.context.get("already_called", False):
            ret_num = random.randint(0, 2)
        else:
            ret_num = random.randint(0, 3)

        rt.context.put("already_called", True)

        return Response(
            message=rt.llm.AssistantMessage(content=str(ret_num)),
            message_info=MessageInfo(
                input_tokens=42,
                output_tokens=42,
                latency=1.42,
                model_name="mock_model",
                total_cost=0.00042,
                system_fingerprint="fp_4242424242",
            ),
        )

    model = mock_llm()
    model._chat = random_number
    # =======================================

    with rt.Session(logging_setting="NONE") as session:
        await rt.call(planner_with_llm_node, llm=model)

    try:
        validate(session.payload(), json_state_schema)
    except ValidationError:
        raise
