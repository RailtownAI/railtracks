from typing import Dict, List, Any, Tuple
from uuid import uuid4

from requestcompletion.run.state.request import (
    RequestTemplate,
)
from requestcompletion.run.tools.profiling import Stamp


def create_tree_from_graph(graph: Dict[str, List[Tuple[str, Any]]]):
    request_list = []
    basic_stamp = Stamp(step=0, time=0, identifier="No detail")
    for source_id, sink_ids in graph.items():
        for sink_id, output in sink_ids:
            request_list.append(
                RequestTemplate(
                    identifier=str(uuid4()),
                    source_id=source_id,
                    sink_id=sink_id,
                    parent=None,
                    stamp=basic_stamp,
                    output=output,
                )
            )

    return request_list


def test_simple_graph_downstream():
    graph = {
        "A": [("B", None), ("C", None)],
        "B": [("D", None)],
        "C": [("E", None)],
        "D": [("F", None)],
        "E": [("G", None)],
    }
    requests = create_tree_from_graph(graph)
    downstream = RequestTemplate.downstream(requests, "A")
    assert len(downstream) == 2
    assert {x.sink_id for x in downstream} == {"B", "C"}
    assert all(x.source_id == "A" for x in downstream)


def test_simple_graph_recursive_downstream():
    graph = {
        "A": [("B", None), ("C", None)],
        "B": [("D", None)],
        "C": [("E", None)],
        "D": [("F", None)],
        "E": [("G", None)],
    }
    requests = create_tree_from_graph(graph)
    downstream = RequestTemplate.all_downstream(requests, "A")
    print([(x.source_id, x.sink_id) for x in downstream])
    assert len(downstream) == 6
    assert {(x.source_id, x.sink_id) for x in downstream} == {
        ("A", "B"),
        ("A", "C"),
        ("B", "D"),
        ("C", "E"),
        ("D", "F"),
        ("E", "G"),
    }


def test_complex_downstream():
    graph = {
        "A": [("B", None), ("C", None)],
        "B": [("D", None), ("E", None)],
        "C": [("F", None)],
        "D": [("H", None), ("I", None), ("J", None), ("K", None)],
        "E": [("L", None)],
        "F": [("N", None), ("M", None)],
        "L": [("O", None), ("P", None)],
        "M": [("Q", None)],
        "N": [("R", None)],
    }

    requests = create_tree_from_graph(graph)
    downstream_of_e = RequestTemplate.downstream(requests, "E")
    assert {(x.source_id, x.sink_id) for x in downstream_of_e} == {("E", "L")}

    downstream_of_l = RequestTemplate.downstream(requests, "L")
    assert {(x.source_id, x.sink_id) for x in downstream_of_l} == {
        ("L", "O"),
        ("L", "P"),
    }

    downstream_of_d = RequestTemplate.downstream(requests, "D")
    assert {(x.source_id, x.sink_id) for x in downstream_of_d} == {
        ("D", "H"),
        ("D", "I"),
        ("D", "J"),
        ("D", "K"),
    }


def test_complex_recursive_downstream():
    graph = {
        "A": [("B", None), ("C", None)],
        "B": [("D", None), ("E", None)],
        "C": [("F", None)],
        "D": [("H", None), ("I", None), ("J", None), ("K", None)],
        "E": [("L", None)],
        "F": [("N", None), ("M", None)],
        "L": [("O", None), ("P", None)],
        "M": [("Q", None)],
        "N": [("R", None)],
    }

    requests = create_tree_from_graph(graph)

    downstream_of_a = RequestTemplate.all_downstream(requests, "A")
    assert {(x.source_id, x.sink_id) for x in downstream_of_a} == {
        ("A", "B"),
        ("A", "C"),
        ("B", "D"),
        ("B", "E"),
        ("C", "F"),
        ("D", "H"),
        ("D", "I"),
        ("D", "J"),
        ("D", "K"),
        ("E", "L"),
        ("F", "N"),
        ("F", "M"),
        ("L", "O"),
        ("L", "P"),
        ("M", "Q"),
        ("N", "R"),
    }

    downstream_of_l = RequestTemplate.all_downstream(requests, "L")
    assert {(x.source_id, x.sink_id) for x in downstream_of_l} == {
        ("L", "O"),
        ("L", "P"),
    }

    downstream_of_c = RequestTemplate.all_downstream(requests, "C")
    assert {(x.source_id, x.sink_id) for x in downstream_of_c} == {
        ("C", "F"),
        ("F", "N"),
        ("F", "M"),
        ("N", "R"),
        ("M", "Q"),
    }


def test_open_tails_simple():
    simple_graph = {
        "A": [("B", None), ("C", None)],
        "B": [("D", None)],
        "C": [("E", None)],
        "D": [("F", None)],
        "E": [("G", None)],
    }

    requests = create_tree_from_graph(simple_graph)
    open_tails = RequestTemplate.open_tails(requests, "A")
    assert {(x.source_id, x.sink_id) for x in open_tails} == {("D", "F"), ("E", "G")}


def test_open_tails_some_complete():
    simple_graph = {
        "A": [("B", None), ("C", None)],
        "B": [("D", None)],
        "C": [("E", None)],
        "D": [("F", None)],
        "E": [("G", str("hello world"))],
    }

    requests = create_tree_from_graph(simple_graph)
    open_tails = RequestTemplate.open_tails(requests, "A")
    assert {(x.source_id, x.sink_id) for x in open_tails} == {("C", "E"), ("D", "F")}


def test_open_tails_fully_complete():
    simple_graph = {
        "A": [("B", True), ("C", True)],
        "B": [("D", True)],
        "C": [("E", True)],
        "D": [("F", True)],
        "E": [("G", True)],
    }

    requests = create_tree_from_graph(simple_graph)

    open_tails = RequestTemplate.open_tails(requests, "A")
    assert len(open_tails) == 0
