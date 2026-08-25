import pytest
import railtracks as rt
import uuid
import asyncio
from railtracks.nodes.nodes import DebugDetails, NodeState, Node, LatencyDetails
from railtracks.exceptions import NodeCreationError

class CapitalizeText(Node[..., str]):
    def __init__(self, string: str):
        self.string = string
        super().__init__()

    async def invoke(self) -> str:
        return self.string.capitalize()

    @classmethod
    def name(cls) -> str:
        return "Capitalize Text"

    @classmethod
    def type(cls):
        return "Tool"

    @classmethod
    def tool_info(cls):
        raise NotImplementedError()

    @classmethod
    def prepare_tool(cls, params):
        return cls(params['string'])

class ErrorNode(Node[..., str]):
    @classmethod
    def name(cls) -> str:
        return "ErrorNode"
    async def invoke(self) -> str:
        raise ValueError("fail")
    @classmethod
    def type(cls):
        return "Tool"

def test_node_state_instantiate():
    node = CapitalizeText("abc")
    state = NodeState(node)
    assert state.instantiate() == node

def test_debugdetails_dict():
    d = DebugDetails()
    d['x'] = 1
    assert d['x'] == 1
    assert isinstance(d, dict)

def test_latency_details():
    l = LatencyDetails(1.23)
    assert l.total_time == 1.23



def test_node_safe_copy():
    node = CapitalizeText("abc")
    copy = node.safe_copy()
    assert copy is not node
    assert copy.name() == node.name()

def test_node_repr():
    node = CapitalizeText("abc")
    rep = repr(node)
    assert "Capitalize Text" in rep
    assert hex(id(node)) in rep

def test_node_uuid():
    node = CapitalizeText("abc")
    uuid_obj = uuid.UUID(node.uuid)
    assert str(uuid_obj) == node.uuid

@pytest.mark.asyncio
async def test_node_tracked_invoke_success():
    node = CapitalizeText("abc")
    result = await node.wrapped_invoke()
    assert result == "Abc"

@pytest.mark.asyncio
async def test_node_tracked_invoke_error():
    node = ErrorNode()
    with pytest.raises(ValueError):
        await node.wrapped_invoke()

def test_node_creation_meta_checks():
    # name is not classmethod
    with pytest.raises(NodeCreationError):
        class BadNode(Node[..., str]):
            def name(cls): return "nope"
            async def invoke(self): return "x"
            @classmethod
            def type(cls): return "Tool"
    # tool_info is not classmethod
    with pytest.raises(NodeCreationError):
        class BadNode2(Node[..., str]):
            @classmethod
            def name(cls): return "Good"
            def tool_info(): pass
            async def invoke(self): return "y"
            @classmethod
            def type(cls): return "Tool"

def test_node_prepare_tool_classmethod():
    node = CapitalizeText.prepare_tool({'string': 'zzz'})
    assert isinstance(node, CapitalizeText)
    assert node.string == 'zzz'
    assert getattr(CapitalizeText.prepare_tool, '__self__', None) is CapitalizeText

def test_nodestate_roundtrip():
    node = CapitalizeText("abc")
    state = NodeState(node)
    node2 = state.instantiate()
    assert node2 is node

