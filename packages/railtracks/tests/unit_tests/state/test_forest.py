import pytest
from dataclasses import dataclass

from railtracks.utils.profiling import Stamp
from railtracks.state.forest import Forest


# ================= START __getitem__, __contains__ tests ============

def test_illegal_access(forest):
    with pytest.raises(TypeError):
        _ = forest[10]

def test_unknown_element(forest):
    with pytest.raises(KeyError):
        _ = forest["unknown"]

def test_forested_contains(forest, unique_id, mock_linked_object):
    the_id = unique_id()
    obj = mock_linked_object(identifier=the_id, message="Hi", stamp=Stamp(21, 0, "x"), parent=None)
    forest._update_heap(obj)
    assert the_id in forest
    assert "something_else" not in forest

# ================ END __getitem__, __contains__ tests ===============

# ================= START forest heap/structure tests ============
def test_simple_operations(forest, unique_id, mock_linked_object):
    id1 = unique_id()
    obj = mock_linked_object(id1, "Hello world", Stamp(901, 0, "Init"), None)
    forest._update_heap(obj)
    assert forest[obj.identifier].message == obj.message
    assert forest[obj.identifier].stamp == obj.stamp
    assert forest[obj.identifier].parent is None

def test_heap(example_structure):
    forest, data = example_structure
    heap = forest.heap()
    assert heap[data["1"][-1].identifier] == data["1"][-1]
    assert heap[data["2"][-1].identifier] == data["2"][-1]
    assert heap[data["3"][-1].identifier] == data["3"][-1]

# ================ END forest heap/structure tests ===============

# ================= START full_data tests ============
def test_full_data_no_step(example_structure):
    forest, data = example_structure
    full_data = forest.full_data()
    assert len(full_data) == 10
    for d in data.values():
        for obj in d:
            assert obj in full_data

def test_full_data_at_step(example_structure):
    forest, data = example_structure
    full_data = forest.full_data(at_step=1)
    # Only steps <=1, leftmost of each identifier
    assert len(full_data) == 5
    assert data["1"][0] in full_data
    assert data["1"][1] in full_data
    assert data["2"][0] in full_data
    assert data["2"][1] in full_data
    assert data["3"][0] in full_data
# ================ END full_data tests ===============

# ================= START time_machine tests ============
def test_time_machine(example_structure):
    forest, data = example_structure
    forest.time_machine(step=1)
    assert forest[data["1"][-1].identifier] == data["1"][1]
    assert forest[data["2"][-1].identifier] == data["2"][1]
    assert forest[data["3"][-1].identifier] == data["3"][0]

def test_specific_time_machine(example_structure):
    forest, data = example_structure
    i_1 = data["1"][-1].identifier
    i_2 = data["2"][-1].identifier
    i_3 = data["3"][-1].identifier

    forest.time_machine(step=2, item_list=[i_3])
    assert forest[i_1] == data["1"][-1]
    assert forest[i_2] == data["2"][-1]
    assert forest[i_3] == data["3"][1]

def test_no_step_time_machine(example_structure):
    forest, data = example_structure
    i_1 = data["1"][-1].identifier
    i_2 = data["2"][-1].identifier
    i_3 = data["3"][-1].identifier

    forest.time_machine(step=None)
    assert forest[i_1] == data["1"][-1]
    assert forest[i_2] == data["2"][-1]
    assert forest[i_3] == data["3"][-1]

def test_start_of_time(example_structure):
    forest, data = example_structure
    i_1 = data["1"][-1].identifier
    i_2 = data["2"][-1].identifier
    i_3 = data["3"][-1].identifier

    forest.time_machine(step=0)
    assert forest[i_1] == data["1"][0]
    assert forest[i_2] == data["2"][0]
    assert i_3 not in forest
# ================ END time_machine tests ===============

# ================= START heap update/validation tests ============

def test_update_operation(forest, unique_id, mock_linked_object):
    id1 = unique_id()
    obj_base = mock_linked_object(id1, "Hello world", Stamp(901, 0, "Init"), None)
    forest._update_heap(obj_base)
    assert forest[obj_base.identifier].message == obj_base.message
    new_obj = mock_linked_object(id1, "Hello world", Stamp(902, 1, "Init"), obj_base)
    forest._update_heap(new_obj)
    assert forest[new_obj.identifier].parent == obj_base
    assert forest[new_obj.identifier].stamp == new_obj.stamp

def test_add_same_object(forest, unique_id, mock_linked_object):
    id1 = unique_id()
    obj = mock_linked_object(id1, "Hello world", Stamp(901, 0, "Init"), None)
    forest._update_heap(obj)
    # Adding exactly same object again
    with pytest.raises(AssertionError):
        forest._update_heap(obj)
    # Adding another object with same id but wrong/no parent
    with pytest.raises(AssertionError):
        forest._update_heap(
            mock_linked_object(id1, "Hello world 2", Stamp(901, 1, "Init"), None)
        )

def test_add_bad_stamp(forest, unique_id, mock_linked_object):
    id1 = unique_id()
    obj = mock_linked_object(id1, "Hello world", Stamp(901, 0, "Init"), None)
    forest._update_heap(obj)
    # Add new with *lower* step – should fail
    with pytest.raises(AssertionError):
        forest._update_heap(
            mock_linked_object(id1, "bad", Stamp(900, 0, "Init"), obj)
        )

def test_level_old_reference(forest, unique_id, mock_linked_object):
    id1 = unique_id()
    obj = mock_linked_object(id1, "Hello", Stamp(901, 0, "Init"), None)
    forest._update_heap(obj)
    obj_new = mock_linked_object(id1, "Hello", Stamp(901, 1, "Init"), obj)
    forest._update_heap(obj_new)
    # Should not allow inserting older but same parent again
    obj_stale = mock_linked_object(id1, "Hello", Stamp(901, 0, "Init"), obj)
    with pytest.raises(AssertionError):
        forest._update_heap(obj_stale)

# ================ END heap update/validation tests ===============

# ================= START state save/load tests ====================
def test_state_saving_operation(forest, unique_id, mock_linked_object):
    id1 = unique_id()
    obj = mock_linked_object(id1, "Hello world", Stamp(901, 0, "Init"), None)
    forest._update_heap(obj)
    state = forest.__getstate__()
    forest2 = Forest[mock_linked_object]()
    forest2.__setstate__(state)
    # Should restore same object (assert equality, not reference)
    assert forest2[obj.identifier] == obj
    # Test adding new version after state restore
    obj2 = mock_linked_object(id1, "Hello world v2", Stamp(901, 1, "Init"), forest2[obj.identifier])
    forest2._update_heap(obj2)
    assert forest2[obj2.identifier].parent == obj
    assert forest2[obj2.identifier].message == "Hello world v2"
# ================ END state save/load tests ======================

# ================= START full_data filtering test (extra) =================
def test_at_step_full_data(example_structure):
    # This appears duplicated with test_full_data_at_step, but retained as requested
    forest, data = example_structure
    full_data = forest.full_data(at_step=1)
    assert len(full_data) == 5
    assert data["1"][0] in full_data
    assert data["1"][1] in full_data
    assert data["2"][0] in full_data
    assert data["2"][1] in full_data
    assert data["3"][0] in full_data
# ================ END full_data filtering test (extra) ==================

# ================= START additional/edge coverage ===========
def test_update_heap_parent_not_latest(forest, unique_id, mock_linked_object):
    # Should not allow inserting with parent not current in heap
    id1 = unique_id()
    obj = mock_linked_object(id1, "o", Stamp(1, 0, "a"), None)
    forest._update_heap(obj)
    # Attempt using a parent that's NOT latest (should raise)
    old_obj = mock_linked_object(id1, "older", Stamp(1, 1, "b"), obj)
    # Normally add the valid successor
    forest._update_heap(old_obj)
    skipped_obj = mock_linked_object(id1, "skip", Stamp(1, 2, "skip"), obj)  # parent should be latest!
    with pytest.raises(AssertionError):
        forest._update_heap(skipped_obj)

def test_time_machine_removes_if_no_step(forest, unique_id, mock_linked_object):
    # Confirm time machine removes object if step earlier than all
    id1 = unique_id()
    obj = mock_linked_object(id1, "Hello", Stamp(50, 10, "late"), None)
    forest._update_heap(obj)
    forest.time_machine(1)
    assert id1 not in forest

def test_full_data_is_copy(example_structure):
    forest, _ = example_structure
    full_data1 = forest.full_data()
    full_data2 = forest.full_data()
    assert full_data1 is not full_data2
    assert full_data1 == full_data2
# ================ END additional/edge coverage ===============
