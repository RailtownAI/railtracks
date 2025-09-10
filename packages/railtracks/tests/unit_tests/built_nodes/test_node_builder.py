import pytest
from unittest.mock import MagicMock, patch
from railtracks.built_nodes._node_builder import NodeBuilder, classmethod_preserving_function_meta

class DummyNode:
    pass

class DummyLLM(DummyNode):
    pass

class DummyFunctionNode(DummyNode):
    pass

def dummy_func(x):
    return x

def test_nodebuilder_basic_build():
    builder = NodeBuilder(DummyNode, name="TestNode", class_name="CustomNode")
    node_cls = builder.build()
    assert issubclass(node_cls, DummyNode)
    assert node_cls.__name__ == "CustomNode"
    assert node_cls.name() == "TestNode"

def test_nodebuilder_add_attribute():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.add_attribute("my_attr", 42, make_function=False)
    node_cls = builder.build()
    assert node_cls.my_attr == 42
    builder.add_attribute("my_method", lambda cls: 99, make_function=True)
    node_cls2 = builder.build()
    assert node_cls2.my_method() == 99

def test_nodebuilder_llm_base():
    builder = NodeBuilder(DummyLLM, name="LLMNode")
    with patch("railtracks.built_nodes._node_builder.SystemMessage", lambda x: x), \
         patch("railtracks.built_nodes._node_builder._check_system_message"):
        builder.llm_base(llm="mock_llm", system_message="sysmsg")
    node_cls = builder.build()
    assert node_cls.get_llm() == "mock_llm"
    assert node_cls.system_message() == "sysmsg"

def test_nodebuilder_structured():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.structured(str)
    node_cls = builder.build()
    assert node_cls.output_schema() == str

def test_nodebuilder_tool_calling_llm():
    with patch("railtracks.built_nodes._node_builder.function_node", lambda f: MagicMock(node_type=f)), \
         patch("railtracks.built_nodes._node_builder._check_max_tool_calls"), \
         patch("railtracks.built_nodes._node_builder.check_connected_nodes"):
        builder = NodeBuilder(DummyFunctionNode, name="ToolNode")
        builder.tool_calling_llm({dummy_func}, max_tool_calls=2)
        node_cls = builder.build()
        assert dummy_func in node_cls.tool_nodes()
        assert node_cls.max_tool_calls == 2

def test_nodebuilder_chat_ui():
    builder = NodeBuilder(DummyNode, name="TestNode")
    mock_chatui = MagicMock()
    builder.chat_ui(mock_chatui)
    node_cls = builder.build()
    assert node_cls.chat_ui == mock_chatui

def test_nodebuilder_setup_function_node():
    with patch("railtracks.built_nodes._node_builder.TypeMapper", lambda f: "type_mapper"), \
         patch("railtracks.built_nodes._node_builder.Tool", MagicMock(from_function=lambda *a, **kw: "tool_obj")):
        builder = NodeBuilder(DummyFunctionNode, name="FuncNode")
        builder.setup_function_node(dummy_func, tool_details="details", tool_params=["param"])
        node_cls = builder.build()
        assert node_cls.type_mapper() == "type_mapper"
        assert node_cls.func(1) == 1
        assert node_cls.tool_info() == "tool_obj"

def test_nodebuilder_tool_callable_llm():
    with patch("railtracks.built_nodes._node_builder._check_tool_params_and_details"), \
         patch("railtracks.built_nodes._node_builder._check_duplicate_param_names"), \
         patch("railtracks.built_nodes._node_builder.LLMBase", DummyLLM):
        builder = NodeBuilder(DummyLLM, name="LLMNode")
        builder.tool_callable_llm(tool_details="details", tool_params={"param"})
        node_cls = builder.build()
        assert hasattr(node_cls, "tool_info")
        assert hasattr(node_cls, "prepare_tool")

def test_nodebuilder_override_tool_info():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.override_tool_info(tool="tool_obj")
    node_cls = builder.build()
    assert node_cls.tool_info() == "tool_obj"
    builder2 = NodeBuilder(DummyNode, name="TestNode")
    builder2.override_tool_info(tool_details="details", tool_params={"param"})
    node_cls2 = builder2.build()
    assert hasattr(node_cls2, "tool_info")

def test_nodebuilder_add_attribute_override_warning():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.add_attribute("my_attr", 42, make_function=False)
    # Should warn on override
    with patch("warnings.warn") as warn_mock:
        builder.add_attribute("my_attr", 99, make_function=False)
        warn_mock.assert_called_once()

def test_classmethod_preserving_function_meta():
    def f(x): return x + 1
    cm = classmethod_preserving_function_meta(f)
    class Dummy:
        pass
    Dummy.f = cm
    assert Dummy.f(2) == 3
