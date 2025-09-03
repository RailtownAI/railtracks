import time

import pytest
from railtracks.state.request import (
    RequestTemplate, RequestForest, RequestDoesNotExistError,
    RequestAlreadyExistsError, Cancelled, Failure,
)
from railtracks.utils.profiling import Stamp



# ================ START RequestTemplate unit tests ======================
def test_repr_and_properties(req_template_factory):
    r = req_template_factory(output=None)
    assert "RequestTemplate" in repr(r)
    assert r.closed is False
    assert r.status == "Open"
    assert r.is_insertion is (r.source_id is not None or False)
    # Set output to close
    completed = req_template_factory(output="OK!", parent=r)
    assert completed.closed is True
    assert completed.status == "Completed"
    assert completed.parent == r

def test_to_edge_and_hierarchy(req_template_factory):
    parent = req_template_factory(step=2, output=123)
    child = req_template_factory(step=3, parent=parent, output=None)
    edge = child.to_edge()
    assert edge.source == child.source_id
    assert edge.target == child.sink_id
    assert edge.details["status"] == child.status
    assert edge.details["output"] == child.output
    assert edge.parent is not None
    assert edge.parent.identifier == parent.identifier

def test_get_all_parents_and_terminal_parent(req_template_factory):
    leaf = req_template_factory(step=3)
    mid = req_template_factory(step=2, parent=leaf)
    root = req_template_factory(step=1, parent=mid)
    parents = root.get_all_parents()
    assert parents == [root, mid, leaf]
    t = root.get_terminal_parent
    assert t == leaf

def test_duration_detail(req_template_factory, req_stamp):
    leaf = req_template_factory(step=1)
    mid = req_template_factory(step=5, parent=leaf)
    assert mid.duration_detail == req_stamp(5).time - req_stamp(1).time

def test_generate_id_unique():
    ids = {RequestTemplate.generate_id() for _ in range(100)}
    assert len(ids) == 100

def test_children_complete_and_downstream_upstream(req_template_factory):
    r1 = req_template_factory(source_id=None, sink_id="A", output=1, step=1)
    r2 = req_template_factory(source_id="A", sink_id="B", output=None, step=2)
    r3 = req_template_factory(source_id="A", sink_id="C", output="done", step=3)
    requests = [r1, r2, r3]
    # children_complete
    assert not RequestTemplate.children_complete(requests, "A")
    # close all, should be true:
    r2c = req_template_factory(source_id="A", sink_id="B", output="x", step=4)
    assert RequestTemplate.children_complete([r1, r2c, r3], "A")
    # downstream: r2, r3 both with source_id="A"
    ds = RequestTemplate.downstream(requests, "A")
    assert {r.sink_id for r in ds} == {"B", "C"}
    # upstream: r1 with sink_id="A"
    us = RequestTemplate.upstream(requests, "A")
    assert us[0].sink_id == "A"

def test_all_downstream_collects_recursively(req_template_factory):
    # A -> B, A -> C, B -> D, C -> E
    A = req_template_factory(source_id=None, sink_id="A", step=1)
    B = req_template_factory(source_id="A", sink_id="B", step=2)
    C = req_template_factory(source_id="A", sink_id="C", step=2)
    D = req_template_factory(source_id="B", sink_id="D", step=3)
    E = req_template_factory(source_id="C", sink_id="E", step=4)
    requests = [A, B, C, D, E]
    results = RequestTemplate.all_downstream(requests, "A")
    assert {x.sink_id for x in results} == {"B", "C", "D", "E"}
# ================ END RequestTemplate unit tests ========================

# =============== START open_tails structure tests ===============
def test_open_tails_starting_from_subtree(req_template_factory):
    # Build a chain F->G->H (all open), only H should be the open tail
    F = req_template_factory(source_id=None, sink_id="F", output=None, step=1)
    G = req_template_factory(source_id="F", sink_id="G", output=None, step=2)
    H = req_template_factory(source_id="G", sink_id="H", output=None, step=3)
    all_reqs = [F, G, H]
    tails = RequestTemplate.open_tails(all_reqs, "F")
    assert len(tails) == 1
    assert tails[0].sink_id == "H"
    # If we close H, then G becomes tail
    Hc = req_template_factory(source_id="G", sink_id="H", output="y", step=3)
    all_reqs = [F, G, Hc]
    tails2 = RequestTemplate.open_tails(all_reqs, "F")
    assert len(tails2) == 1 and tails2[0].sink_id == "G"

def test_open_tails_no_open_leaves(req_template_factory):
    I = req_template_factory(source_id=None, sink_id="I", output="closed", step=1)
    assert RequestTemplate.open_tails([I], None) == []

def test_open_tails_deep_structure(req_template_factory):
    # Deep chain with one open in the middle
    J = req_template_factory(source_id=None, sink_id="J", output=None, step=1)
    K = req_template_factory(source_id="J", sink_id="K", output=None, step=2)
    L = req_template_factory(source_id="K", sink_id="L", output="closed", step=3)
    all_reqs = [J, K, L]
    tails = RequestTemplate.open_tails(all_reqs, None)
    # Should return only K (since it's open, child L is closed)
    assert [t.sink_id for t in tails] == ["K"]

def test_open_tails_multiple_starting_points(req_template_factory):
    # Multiple roots
    M = req_template_factory(source_id=None, sink_id="M", output=None, step=1)
    N = req_template_factory(source_id=None, sink_id="N", output="done", step=2)
    res = RequestTemplate.open_tails([M, N], None)
    assert len(res) == 1 and res[0].sink_id == "M"
# =============== END open_tails structure tests ===============

# ================ START RequestForest tests =============================
def test_forest_create_and_prevents_duplicate(req_forest, req_stamp):
    rid = RequestTemplate.generate_id()
    req_forest.create(rid, source_id=None, sink_id='A', input_args=(), input_kwargs={}, stamp=req_stamp(0))
    # Should raise on duplicate
    with pytest.raises(RequestAlreadyExistsError):
        req_forest.create(rid, source_id=None, sink_id='A', input_args=(), input_kwargs={}, stamp=req_stamp(1))

def test_forest_update_and_not_exists(req_forest, req_template_factory, req_stamp):
    # Create and then update
    r = req_template_factory()
    rid = r.identifier
    req_forest._update_heap(r)
    req_forest.update(rid, output="finished!", stamp=req_stamp(1))
    assert req_forest[rid].output == "finished!"
    # Not in heap
    with pytest.raises(RequestDoesNotExistError):
        req_forest.update("nope", output="?", stamp=req_stamp(1))

def test_forest_children_and_children_requests_complete(req_forest, req_template_factory):
    A = req_template_factory(identifier="A", source_id=None, sink_id="A", output="ins", step=1)
    B = req_template_factory(identifier="B", source_id="A", sink_id="B", output="ok", step=2)
    C = req_template_factory(identifier="C", source_id="A", sink_id="C", output="ok", step=3)
    req_forest._update_heap(A)
    req_forest._update_heap(B)
    req_forest._update_heap(C)
    # Should find both B and C as children of A
    children = req_forest.children("A")
    assert set(x.sink_id for x in children) == {"B", "C"}
    # Check children_requests_complete
    got = req_forest.children_requests_complete("A")
    assert got == A.identifier

def test_forest_get_request_from_child_id(req_forest, req_template_factory):
    A = req_template_factory(identifier="A", source_id=None, sink_id="A", output="ins", step=1)
    B = req_template_factory(identifier="B", source_id="A", sink_id="B", output=None, step=2)
    for req in (A, B):
        req_forest._update_heap(req)
    returned = req_forest.get_request_from_child_id("A")
    assert returned == A
    # Not present: should raise
    with pytest.raises(RequestDoesNotExistError):
        req_forest.get_request_from_child_id("X")

def test_forest_open_tails_and_insertion_request(req_forest, req_template_factory):
    A = req_template_factory(identifier="A", source_id=None, sink_id="A", output=None, step=1)
    B = req_template_factory(identifier="B", source_id="A", sink_id="B", output="out", step=2)
    req_forest._update_heap(A)
    req_forest._update_heap(B)
    # Open tails should return A
    tails = req_forest.open_tails()
    assert len(tails) == 1 and tails[0].sink_id == "A"
    # insertion_request returns all with source_id is None
    ins = req_forest.insertion_request
    assert ins and ins[0].sink_id == "A"
    assert req_forest.answer == None # answer property retrieves insertion output

def test_forest_answer_handles_no_insertions(req_forest):
    # Heap is empty
    assert req_forest.answer is None

def test_forest_to_edges_returns_all(req_forest, req_template_factory):
    A = req_template_factory(identifier="A", source_id=None, sink_id="A", output="foo", step=1)
    B = req_template_factory(identifier="B", source_id="A", sink_id="B", step=2, output="bar")
    req_forest._update_heap(A)
    req_forest._update_heap(B)
    edge_list = req_forest.to_edges()
    assert len(edge_list) == 2
    assert {e.source for e in edge_list} == {None, "A"}

def test_forest_generate_graph(req_template_factory):
    # Build three requests: None->A, A->B, A->C
    A = req_template_factory(identifier="A", source_id=None, sink_id="A", step=1)
    B = req_template_factory(identifier="B", source_id="A", sink_id="B", step=2)
    C = req_template_factory(identifier="C", source_id="A", sink_id="C", step=3)
    heap = {r.identifier: r for r in [A, B, C]}
    graph = RequestForest.generate_graph(heap)
    # Edges from None to A (insertion), and from A to B, A to C
    assert (("A", A.identifier) in graph[None])
    assert (("B", B.identifier) in graph["A"])
    assert (("C", C.identifier) in graph["A"])
    # Each node explicitly appears in keys
    assert "B" in graph and "C" in graph
# =============== END RequestForest tests ==============================

# ==================== START Failure and Cancelled tests =================
def test_cancelled_and_failure():
    c = Cancelled()
    assert isinstance(c, Cancelled)
    e = Exception("fail")
    f = Failure(e)
    assert isinstance(f, Failure)
    assert f.exception is e
# =============== END Failure and Cancelled tests ========================



def test_status():
    unfinished_request = RequestTemplate(
        identifier="ahsusu",
        stamp = Stamp(time=time.time(), step=0, identifier="Hello World"),
        parent=None,
        source_id="heghe",
        sink_id="heheuii",
        input=((), {}),
        output=None,
    )

    assert unfinished_request.status == "Open"

def test_status_2():
    completed_request = RequestTemplate(
        identifier="ahsusu",
        stamp=Stamp(time=time.time(), step=0, identifier="Hello World"),
        parent=None,
        source_id="heghe",
        sink_id="heheuii",
        input=((), {}),
        output="example output",
    )
    assert completed_request.status == "Completed"

def test_status_failure():
    failed_request = RequestTemplate(
        identifier="ahsusu",
        stamp=Stamp(time=time.time(), step=0, identifier="Hello World"),
        parent=None,
        source_id="heghe",
        sink_id="heheuii",
        input=((), {}),
        output=Failure(Exception("example")),
    )

    assert failed_request.status == "Failed"
