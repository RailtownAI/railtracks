import pytest

from railtracks.nodes.tool_callable import ToolCallable

# ================= START ToolCallable tests ============

class DummyToolCallable(ToolCallable):
    @classmethod
    def tool_info(cls):
        return "dummy_tool"  # Simulate returning a Tool object

    def __init__(self, value=None, other=None):
        self.value = value
        self.other = other


def test_tool_info_not_implemented_in_base_class():
    with pytest.raises(NotImplementedError):
        ToolCallable.tool_info()

def test_tool_info_implemented_in_subclass():
    assert DummyToolCallable.tool_info() == "dummy_tool"

def test_prepare_tool_creates_instance_from_parameters():
    params = {"value": 42, "other": "abc"}
    instance = DummyToolCallable.prepare_tool(**params)
    assert isinstance(instance, DummyToolCallable)
    assert instance.value == 42
    assert instance.other == "abc"

def test_prepare_tool_with_no_parameters():
    instance = DummyToolCallable.prepare_tool()
    assert isinstance(instance, DummyToolCallable)
    assert instance.value is None
    assert instance.other is None

# ================ END ToolCallable tests ===============