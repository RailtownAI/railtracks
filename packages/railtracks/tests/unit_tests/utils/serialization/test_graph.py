import pytest
from railtracks.utils.serialization.graph import Edge, Vertex

# ================= START Edge tests =====================

def test_edge_instantiation_minimal(fake_stamp):
    edge = Edge(
        identifier="edge-id",
        source="A",
        target="B",
        stamp=fake_stamp,
        details={"foo": "bar"},
        parent=None
    )
    assert edge.identifier == "edge-id"
    assert edge.source == "A"
    assert edge.target == "B"
    assert edge.stamp is fake_stamp
    assert edge.details == {"foo": "bar"}
    assert edge.parent is None

def test_edge_instantiation_with_parent(fake_stamp):
    parent = Edge(
        identifier="eid",
        source="SRC",
        target="TGT",
        stamp=fake_stamp,
        details={"par": "ent"},
        parent=None
    )
    child = Edge(
        identifier="eid",
        source="SRC",
        target="TGT",
        stamp=fake_stamp,
        details={},
        parent=parent
    )
    assert child.parent is parent
    assert child.identifier == parent.identifier
    assert child.source == parent.source
    assert child.target == parent.target

def test_edge_parent_identifier_mismatch_raises(fake_stamp):
    parent = Edge(
        identifier="x1",
        source="src",
        target="tgt",
        stamp=fake_stamp,
        details={},
        parent=None
    )
    with pytest.raises(AssertionError, match="parent identifier must match"):
        Edge(
            identifier="x2",
            source="src",
            target="tgt",
            stamp=fake_stamp,
            details={},
            parent=parent
        )

def test_edge_parent_source_target_mismatch_raises(fake_stamp):
    parent = Edge(
        identifier="abc",
        source="SRC",
        target="A",
        stamp=fake_stamp,
        details={},
        parent=None
    )
    with pytest.raises(AssertionError, match="parent edge must have the same source and target"):
        Edge(
            identifier="abc",
            source="SRC",
            target="OTHER",
            stamp=fake_stamp,
            details={},
            parent=parent
        )

def test_edge_allows_none_identifier_or_source(fake_stamp):
    # Identifiers can be None for root/anonymous edges
    edge = Edge(
        identifier=None,
        source=None,
        target="X",
        stamp=fake_stamp,
        details={},
        parent=None
    )
    assert edge.identifier is None
    assert edge.source is None
    assert edge.target == "X"

# ================= END Edge tests =======================

# ================ START Vertex tests ===================

def test_vertex_instantiation_minimal(fake_stamp):
    v = Vertex(
        identifier="nid",
        node_type="typeA",
        name="Vertex Name",
        stamp=fake_stamp,
        details={"abc": 1},
        parent=None,
    )
    assert v.identifier == "nid"
    assert v.node_type == "typeA"
    assert v.stamp is fake_stamp
    assert v.details == {"abc": 1}
    assert v.parent is None

def test_vertex_with_parent_identifier_must_match(fake_stamp):
    parent = Vertex(
        identifier="n1",
        name="Parent Vertex",
        node_type="T",
        stamp=fake_stamp,
        details={},
        parent=None,
    )
    v = Vertex(
        identifier="n1",
        node_type="T",
        name="Child Vertex",
        stamp=fake_stamp,
        details={},
        parent=parent,
    )
    assert v.parent is parent

def test_vertex_parent_identifier_mismatch_raises(fake_stamp):
    parent = Vertex(
        identifier="z1",
        node_type="T",
        name="Parent Vertex",
        stamp=fake_stamp,
        details={},
        parent=None,
    )
    with pytest.raises(AssertionError, match="parent identifier must match"):
        Vertex(
            identifier="z2",
            node_type="T",
            name="Child Vertex",
            stamp=fake_stamp,
            details={},
            parent=parent,
        )

# ================ END Vertex tests =====================