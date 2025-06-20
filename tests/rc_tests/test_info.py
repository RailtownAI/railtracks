import pytest

from requestcompletion.info import ExecutionInfo


def confirm_empty(info: ExecutionInfo):
    """
    Helper function to confirm that the ExecutionInfo instance is empty.
    """
    assert len(info.request_heap.heap()) == 0
    assert len(info.node_heap.heap()) == 0
    assert info.exception_history == []
    assert info.stamper._step == 0
    assert info.all_stamps == []
    assert info.answer is None
    assert info.insertion_requests == []
    assert info.get_info() == info
    with pytest.raises(ValueError):
        info.get_info(ids=["Not an id"])


def test_empty_starter():
    info = ExecutionInfo.create_new()
    confirm_empty(info)


def test_default():
    """
    Test the default method of ExecutionInfo.
    """
    info = ExecutionInfo.default()
    confirm_empty(info)

