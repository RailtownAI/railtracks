import pytest

from railtracks.state.utils import create_sub_state_info

# ================= START create_sub_state_info tests =============

# ---------------- Single parent extraction -----------------------
def test_extract_single_parent_branch(req_template_factory, linked_node_factory):
    # Tree: root->A, A->B, A->C
    r_root = req_template_factory(identifier="r0", source_id=None, sink_id="A", step=1, output="root")
    r_b = req_template_factory(identifier="r1", source_id="A", sink_id="B", step=2)
    r_c = req_template_factory(identifier="r2", source_id="A", sink_id="C", step=3)
    heap = {x.identifier: x for x in [r_root, r_b, r_c]}

    nodes = {
        "A": linked_node_factory("A", r_root.stamp),
        "B": linked_node_factory("B", r_b.stamp),
        "C": linked_node_factory("C", r_c.stamp),
    }

    result = create_sub_state_info(nodes, heap, "r0")
    # Should include all three requests and all three nodes
    assert set(result.request_forest._heap) == {"r0", "r1", "r2"}
    assert set(result.node_forest._heap) == {"A", "B", "C"}

# -------------- Multiple parents and assertion error -------------
def test_multiple_parents_duplicate_id_assertion(req_template_factory, linked_node_factory):
    # Overlapping branches: both parents include a node/request "C"
    r1 = req_template_factory(identifier="r1", source_id=None, sink_id="A", step=1)
    r2 = req_template_factory(identifier="r2", source_id=None, sink_id="B", step=1)
    rt1 = req_template_factory(identifier="rc1", source_id="A", sink_id="C", step=2)
    rt2 = req_template_factory(identifier="rc2", source_id="B", sink_id="C", step=3)
    heap = {x.identifier: x for x in [r1, r2, rt1, rt2]}
    nodes = {
        "A": linked_node_factory("A", r1.stamp),
        "B": linked_node_factory("B", r2.stamp),
        "C": linked_node_factory("C",rt1.stamp),
    }
    # Should raise due to duplicate "C"
    with pytest.raises(AssertionError):
        create_sub_state_info(nodes, heap, ["r1", "r2"])

# ------------ Nodes missing from heap are not in result ----------
def test_missing_nodes_are_not_selected(req_template_factory, linked_node_factory):
    # Node "B" missing from original heap, but referenced by request
    r1 = req_template_factory(identifier="r1", source_id=None, sink_id="A", step=1)
    r2 = req_template_factory(identifier="r2", source_id="A", sink_id="B", step=2)
    heap = {x.identifier: x for x in [r1, r2]}
    nodes = {"A": linked_node_factory("A", r1.stamp)}
    res = create_sub_state_info(nodes, heap, "r1")
    # Request for B is included, but node "B" is missing
    assert "B" not in res.node_forest._heap
    assert "r2" in res.request_forest._heap

# ---- Multiple non-overlapping parents success case ----
def test_multiple_nonoverlapping_parents(req_template_factory, linked_node_factory):
    # Disjoint subgraphs, both included
    ra = req_template_factory(identifier="ra", source_id=None, sink_id="A", step=1)
    rb = req_template_factory(identifier="rb", source_id=None, sink_id="B", step=1)
    heap = {x.identifier: x for x in [ra, rb]}
    nodes = {"A": linked_node_factory("A", ra.stamp), "B": linked_node_factory("B", rb.stamp)}
    result = create_sub_state_info(nodes, heap, ["ra", "rb"])
    assert set(result.node_forest._heap) == {"A", "B"}
    assert set(result.request_forest._heap) == {"ra", "rb"}

# ------------ Empty parent(s) or heap ------------------
def test_empty_parent_or_heap(linked_node_factory):
    # no requests, no nodes
    res = create_sub_state_info({}, {}, [])
    assert not res.node_forest._heap
    assert not res.request_forest._heap

    # valid request_forest but missing parent id
    r = {}
    n = {}
    assert not create_sub_state_info(n, r, []).node_forest._heap

# =============== END create_sub_state_info tests =============