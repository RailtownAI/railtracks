import pytest
import railtracks as rt
import uuid
import asyncio
from railtracks.nodes.nodes import DebugDetails, NodeState, Node
from railtracks.exceptions import NodeCreationError
# ========== DUMMY NODES ==========
class CapitalizeText(Node[str]):
    def __init__(self, string: str, debug_details=None):
        self.string = string
        super().__init__(debug_details=debug_details)

    async def invoke(self) -> str:
        return self.string.capitalize()
    
    @classmethod
    def name(cls) -> str:
        return "Capitalize Text"
    
    @classmethod
    def type(cls):
        return "Tool"
    
    

class AbstractNode(Node[int]):
    @classmethod
    def name(cls) -> str:
        return "Abstract"
    
    async def invoke(self) -> int:
        raise NotImplementedError
    
    @classmethod
    def type(cls):
        raise NotImplementedError

# ============== FIXTURES ==============

@pytest.fixture
def sample_string():
    return "hello world"

@pytest.fixture
def cap_node(sample_string):
    return CapitalizeText(sample_string)

@pytest.fixture
def empty_string_node():
    return CapitalizeText("")

@pytest.fixture
def debug_details():
    return DebugDetails(foo='bar', baz=5)

# ========== TESTS ==========

@pytest.mark.asyncio
async def test_capitalize_text_invoke(cap_node, sample_string):
    assert await cap_node.invoke() == sample_string.capitalize()
    assert cap_node.name() == "Capitalize Text"

@pytest.mark.asyncio
async def test_capitalize_empty(empty_string_node):
    assert await empty_string_node.invoke() == ""
    assert empty_string_node.name() == "Capitalize Text"

def test_node_details_and_debug(debug_details):
    node = CapitalizeText("something", debug_details=debug_details)
    # Should return the passed DebugDetails
    assert node.details == debug_details
    # Should cope with no debug_details
    node2 = CapitalizeText("anything")
    assert isinstance(node2.details, DebugDetails)

def test_state_details(cap_node):
    details = cap_node.state_details()
    assert isinstance(details, dict)
    # Should stringify all
    for value in details.values():
        assert isinstance(value, str)
    assert 'string' in details

def test_safe_copy(cap_node):
    cap_node.details['foo'] = 'bar'
    node_copy = cap_node.safe_copy()
    # Should deep copy all attributes
    assert node_copy is not cap_node
    assert node_copy.string == cap_node.string
    assert node_copy.__dict__ == cap_node.__dict__
    # Changing a mutable attribute shouldn't affect the other
    node_copy.details['foo'] = 'baz'
    assert cap_node.details['foo'] == 'bar'

def test_uuid_generated(cap_node):
    # UUID is generated and is valid
    uuid_obj = uuid.UUID(cap_node.uuid)
    assert str(uuid_obj) == cap_node.uuid

def test_repr(cap_node):
    rep = repr(cap_node)
    assert "Capitalize Text" in rep
    assert hex(id(cap_node)) in rep

def test_abstract_node_instantiation_raises():
    # Because invoke is implemented, should be instantiable
    n = AbstractNode()
    assert isinstance(n, AbstractNode)
    # But its invoke raises NotImplementedError
    with pytest.raises(NotImplementedError):
        asyncio.run(n.invoke())

def test_not_implemented_tool_info(cap_node):
    with pytest.raises(NotImplementedError):
        cap_node.tool_info()

def test_prepare_tool_and_classmethod_behavior():
    params = {'string': 'zzz'}
    node = CapitalizeText.prepare_tool(params)
    assert isinstance(node, CapitalizeText)
    assert node.string == 'zzz'
    # It's a classmethod
    assert getattr(CapitalizeText.prepare_tool, '__self__', None) is CapitalizeText

def test_nodestate_roundtrip(cap_node):
    state = NodeState(cap_node)
    node2 = state.instantiate()
    assert node2 is cap_node

def test_debugdetails_dict_compatibility():
    d = DebugDetails()
    d['a'] = 1
    assert d['a'] == 1
    assert isinstance(d, dict)

def test_node_creation_meta_checks(monkeypatch):
    # NodeCreationMeta checks: Try making a class with wrong classmethod, breaks
    # Pretty name is NOT classmethod, should error on creation
    with pytest.raises(NodeCreationError):
        class BadNode(Node[str]):
            def name(cls): return "nope"
            async def invoke(self): return "x"

    # tool_info is NOT classmethod, should error on creation
    with pytest.raises(NodeCreationError):
        class BadNode2(Node[str]):
            @classmethod
            def name(cls): return "Good"
            def tool_info(): pass
            async def invoke(self): return "y"

