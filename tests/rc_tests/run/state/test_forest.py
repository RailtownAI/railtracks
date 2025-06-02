import uuid

import pytest
from dataclasses import dataclass

from src.requestcompletion.utils.profiling import Stamp
from src.requestcompletion.state.forest import Forest, AbstractLinkedObject


@dataclass(frozen=True)
class MockLinkedObject(AbstractLinkedObject):
    message: str


@pytest.fixture
def example_structure():
    identifier_1 = str(uuid.uuid4())
    identifier_2 = str(uuid.uuid4())
    identifier_3 = str(uuid.uuid4())

    linked1_1 = MockLinkedObject(identifier_1, Stamp(8091, 0, "Init"), parent=None, message="Hello world")
    linked1_2 = MockLinkedObject(identifier_1, Stamp(8091, 1, "second try"), parent=linked1_1, message="Hello world...")
    linked1_3 = MockLinkedObject(identifier_1, Stamp(8091, 5, "third try"), parent=linked1_2, message="Hello world...!")

    linked2_1 = MockLinkedObject(identifier_2, Stamp(8091, 0, "Init"), parent=None, message="Hello world")
    linked2_2 = MockLinkedObject(identifier_2, Stamp(8091, 1, "second try"), parent=linked2_1, message="Hello world...")

    linked3_1 = MockLinkedObject(identifier_3, Stamp(8091, 1, "Init"), parent=None, message="Hello world")
    linked3_2 = MockLinkedObject(identifier_3, Stamp(8091, 2, "second try"), parent=linked3_1, message="Hello world...")
    linked3_3 = MockLinkedObject(identifier_3, Stamp(8091, 3, "third try"), parent=linked3_2, message="Hello world...!")
    linked3_4 = MockLinkedObject(
        identifier_3, Stamp(8091, 4, "fourth try"), parent=linked3_3, message="Hello world...!!"
    )
    linked3_5 = MockLinkedObject(
        identifier_3, Stamp(8091, 5, "fifth try"), parent=linked3_4, message="Hello world...!!!"
    )

    heap = Forest[MockLinkedObject]()
    heap._update_heap(linked1_1)
    heap._update_heap(linked1_2)
    heap._update_heap(linked1_3)

    heap._update_heap(linked2_1)
    heap._update_heap(linked2_2)

    heap._update_heap(linked3_1)
    heap._update_heap(linked3_2)
    heap._update_heap(linked3_3)
    heap._update_heap(linked3_4)
    heap._update_heap(linked3_5)

    return heap, {
        "1": [linked1_1, linked1_2, linked1_3],
        "2": [linked2_1, linked2_2],
        "3": [linked3_1, linked3_2, linked3_3, linked3_4, linked3_5],
    }


def test_illegal_access():
    f = Forest[MockLinkedObject]()
    with pytest.raises(TypeError):
        _ = f[10]  # noqa: for testing


def test_unknown_element():
    f = Forest[MockLinkedObject]()
    with pytest.raises(KeyError):
        _ = f["unknown"]


def test_simple_operations():
    heap = Forest[MockLinkedObject]()
    message_object = MockLinkedObject(
        identifier=str(uuid.uuid4()),
        message="Hello world",
        stamp=Stamp(901, 0, "Init"),
        parent=None,
    )
    heap._update_heap(message_object)

    assert heap[message_object.identifier].message == message_object.message
    assert heap[message_object.identifier].stamp == message_object.stamp
    assert heap[message_object.identifier].parent is None


def test_heap(example_structure):
    forest, data = example_structure

    heap = forest.heap()

    i_1 = data["1"][-1].identifier
    assert heap[i_1] == data["1"][-1]

    i_2 = data["2"][-1].identifier
    assert heap[i_2] == data["2"][-1]

    i_3 = data["3"][-1].identifier
    assert heap[i_3] == data["3"][-1]


def test_full_data_no_step(example_structure):
    forest, data = example_structure
    full_data = forest.full_data()

    assert len(full_data) == 10

    assert data["1"][0] in full_data
    assert data["1"][1] in full_data
    assert data["1"][2] in full_data

    assert data["2"][0] in full_data
    assert data["2"][1] in full_data

    assert data["3"][0] in full_data
    assert data["3"][1] in full_data
    assert data["3"][2] in full_data
    assert data["3"][3] in full_data
    assert data["3"][4] in full_data


def test_full_data_at_step(example_structure):
    forest, data = example_structure
    full_data = forest.full_data(at_step=1)

    assert len(full_data) == 5

    assert data["1"][0] in full_data
    assert data["1"][1] in full_data

    assert data["2"][0] in full_data
    assert data["2"][1] in full_data

    assert data["3"][0] in full_data


def test_time_machine(example_structure):
    forest, data = example_structure

    forest.time_machine(step=1)

    i_1 = data["1"][-1].identifier
    assert forest[i_1] == data["1"][1]

    i_2 = data["2"][-1].identifier
    assert forest[i_2] == data["2"][1]

    i_3 = data["3"][-1].identifier
    assert forest[i_3] == data["3"][0]


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


def test_state_saving_operation():
    heap = Forest[MockLinkedObject]()

    identifier = str(uuid.uuid4())

    message_object = MockLinkedObject(
        identifier=identifier,
        message="Hello world",
        stamp=Stamp(901, 0, "Init"),
        parent=None,
    )

    heap._update_heap(message_object)

    assert heap[message_object.identifier].message == message_object.message

    state = heap.__getstate__()
    heap2 = Forest[MockLinkedObject]()
    heap2.__setstate__(state)
    heap = heap2

    linked_obj = heap[message_object.identifier]

    updated_obj = MockLinkedObject(
        identifier=identifier,
        message="Hello world",
        stamp=Stamp(901, 1, "Init"),
        parent=linked_obj,
    )

    heap._update_heap(updated_obj)

    assert heap[updated_obj.identifier].parent == linked_obj
    assert heap[updated_obj.identifier].message == updated_obj.message
    assert heap[updated_obj.identifier].stamp == updated_obj.stamp
