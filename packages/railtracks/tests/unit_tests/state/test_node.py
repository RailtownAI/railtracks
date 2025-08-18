# =================== START fixtures for node.py ====================
import pytest
import uuid
from railtracks.state.node import (
    LinkedNode, NodeCopyError,
)
from railtracks.utils.profiling import Stamp

# =============== START LinkedNode basic/tests =====================

def test_linkednode_props(dummy_node_factory, linked_node_factory):
    identifier = str(uuid.uuid4())
    stamp = Stamp(123, 1, "test")
    node = dummy_node_factory(uuid=identifier, details={'x': 42})
    parent = None
    ln = LinkedNode(identifier=identifier, _node=node, stamp=stamp, parent=parent)

    # The .node property should return a copy, not original, and error if copying fails
    node2 = ln.node
    assert isinstance(node2, type(node))
    assert node2._copied is True  # Check it's indeed a "copied" node

def test_linkednode_to_vertex_includes_hierarchy(dummy_node_factory, linked_node_factory):
    base_id = str(uuid.uuid4())
    parent_stamp = Stamp(1, 0, "init")
    parent_ln = linked_node_factory(base_id, parent_stamp, parent=None, pretty='parent', details={'a': 1})
    child_stamp = Stamp(1, 1, "child")
    child_ln = linked_node_factory(base_id, child_stamp, parent=parent_ln, pretty='child', details={'b': 2})

    vertex = child_ln.to_vertex()
    assert vertex.identifier == child_ln.identifier
    assert vertex.name == child_ln.node.name()
    assert vertex.stamp == child_ln.stamp
    assert vertex.parent.identifier == parent_ln.identifier
    assert vertex.node_type == parent_ln.node.type()

def test_linkednode_nodecopyerror_raised_on_safe_copy(monkeypatch, linked_node_factory):
    class UnsafeNode:
        def safe_copy(self):
            raise RuntimeError("fail copy")
        @property
        def pretty_name(self):
            return 'unsafe'

    ln = LinkedNode(
        identifier='id', _node=UnsafeNode(), stamp=Stamp(1, 1, "fail"), parent=None
    )
    with pytest.raises(NodeCopyError):
        _ = ln.node
# =============== END LinkedNode basic/tests =======================

# =============== START NodeForest heap & access ===================
def test_nodeforest_update_and_getitem(node_forest, dummy_node_factory):
    a_id = str(uuid.uuid4())
    stamp = Stamp(1, 2, "s1")
    node = dummy_node_factory(uuid=a_id, pretty='ntype')
    node_forest.update(node, stamp)
    # __getitem__ returns LinkedNode
    linked = node_forest[a_id]
    assert isinstance(linked, LinkedNode)
    assert linked.identifier == a_id
    # Returns a copied node
    n_copied = linked.node
    assert n_copied.uuid == node.uuid
    assert getattr(n_copied, "_copied", False)

def test_nodeforest_multiple_updates_chain(node_forest, dummy_node_factory):
    a_id = str(uuid.uuid4())
    # Add first
    node1 = dummy_node_factory(uuid=a_id, pretty='first')
    stamp1 = Stamp(1, 1, "first")
    node_forest.update(node1, stamp1)
    # Add again (should chain parent)
    node2 = dummy_node_factory(uuid=a_id, pretty='second')
    stamp2 = Stamp(1, 2, "second")
    node_forest.update(node2, stamp2)
    ln2 = node_forest[a_id]
    assert ln2.stamp == stamp2
    assert ln2.parent.stamp == stamp1
    assert ln2.parent.parent is None

def test_nodeforest_id_type_mapping(node_forest, dummy_node_factory):
    a_id = str(uuid.uuid4())
    node = dummy_node_factory(uuid=a_id, pretty='ABrandNewType')
    stamp = Stamp(1, 9, "mapping")
    node_forest.update(node, stamp)
    typ = node_forest.get_node_type(a_id)
    assert typ == type(node)

# =============== END NodeForest heap & access =====================

# =============== START to_vertices & conversions ==================
def test_nodeforest_to_vertices_returns_all(node_forest, dummy_node_factory):
    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())
    stamp1 = Stamp(1, 1, "a")
    stamp2 = Stamp(2, 2, "b")
    node_forest.update(dummy_node_factory(uuid=id1, pretty='nt1'), stamp1)
    node_forest.update(dummy_node_factory(uuid=id2, pretty='nt2'), stamp2)
    vertices = node_forest.to_vertices()
    assert len(vertices) == 2
    ids = {v.identifier for v in vertices}
    assert id1 in ids and id2 in ids

def test_nodeforest_to_vertices_hierarchical(node_forest, dummy_node_factory):
    id1 = str(uuid.uuid4())
    stamp1 = Stamp(1, 1, "root")
    node_forest.update(dummy_node_factory(uuid=id1, pretty='nt1'), stamp1)
    stamp2 = Stamp(1, 2, "child")
    node_forest.update(dummy_node_factory(uuid=id1, pretty='nt1'), stamp2)
    vertices = node_forest.to_vertices()
    # The newest should contain the parent as .parent
    this_vertex = [v for v in vertices if v.stamp == stamp2][0]
    assert this_vertex.parent is not None
    assert this_vertex.parent.identifier == id1
# =============== END to_vertices & conversions ====================