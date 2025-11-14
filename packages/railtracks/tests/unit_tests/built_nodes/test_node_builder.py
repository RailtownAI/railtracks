from pydantic import BaseModel
import pytest
from unittest.mock import MagicMock, patch
from railtracks.built_nodes._node_builder import NodeBuilder, classmethod_preserving_function_meta
from railtracks.built_nodes.concrete import LLMBase, OutputLessToolCallLLM
from railtracks import function_node, ToolManifest
from railtracks.built_nodes.easy_usage_wrappers.function import SyncDynamicFunctionNode
from railtracks.llm import Parameter, Tool, OpenAILLM
from railtracks.llm import SystemMessage
from railtracks.exceptions.errors import NodeCreationError
from railtracks.nodes.nodes import Node

class Schema(BaseModel):
    x: int

def dummy_manifest():
    tool_manifest = ToolManifest(
            description="A tool to be called",
            parameters=[Parameter(
                name="x",
                description="Input to the tool",
                param_type="integer",
            )]
            )
    return tool_manifest
class DummyNode(LLMBase):
    @classmethod
    def name(cls): return "DummyNode"
    async def invoke(self): return "dummy"
    @classmethod
    def type(cls): return "Agent"

class DummyToolCallNode(OutputLessToolCallLLM):
    @classmethod
    def name(cls): return "DummyNode"
    async def invoke(self): return "dummy"
    @classmethod
    def type(cls): return "Agent"

def dummy_func(x):
    return x

def dummy_function_node():
    return function_node(dummy_func)

def llm_model():
    return OpenAILLM(model_name="gpt-4o")

def test_nodebuilder_basic_build():
    builder = NodeBuilder(DummyNode, name="TestNode", class_name="CustomNode")
    node_cls = builder.build()
    assert issubclass(node_cls, DummyNode)
    assert node_cls.__name__ == "CustomNode"
    assert node_cls.name() == "TestNode"

def test_nodebuilder_basic_build_no_names():
    builder = NodeBuilder(DummyNode)
    node_cls = builder.build()
    assert issubclass(node_cls, DummyNode)
    assert node_cls.__name__ == "DynamicDummyNode"
    assert node_cls.name() == "DummyNode"

def test_nodebuilder_add_attribute():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.add_attribute("my_attr", 42, make_function=False)
    node_cls = builder.build()
    assert node_cls.my_attr == 42
    builder.add_attribute("my_method", lambda cls: 99, make_function=True)
    node_cls2 = builder.build()
    assert node_cls2.my_method() == 99

def test_nodebuilder_llm_base():
    builder = NodeBuilder(DummyNode, name="LLMNode", class_name="LLMNode")
    builder.llm_base(llm_model(), system_message="sysmsg")
    node_cls = builder.build()
    assert isinstance(node_cls.get_llm(), type(llm_model()))
    assert node_cls.system_message().content == "sysmsg"
    assert node_cls.system_message().role == "system"

def test_nodebuilder_llm_base_System_message():
    builder = NodeBuilder(DummyNode, name="LLMNode", class_name="LLMNode")
    builder.llm_base(llm_model(), system_message=SystemMessage(content="sysmsg"))
    node_cls = builder.build()
    assert isinstance(node_cls.get_llm(), type(llm_model()))
    assert node_cls.system_message().content == "sysmsg"
    assert node_cls.system_message().role == "system"

def test_nodebuilder_structured():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.llm_base(llm_model(), system_message=SystemMessage(content="sysmsg"))
    builder.structured(Schema)
    node_cls = builder.build()
    assert node_cls.output_schema() == Schema

def test_nodebuilder_tool_calling_llm_with_function():
        builder = NodeBuilder(DummyToolCallNode)
        builder.llm_base(llm_model(), system_message=SystemMessage(content="sysmsg"))
        builder.tool_calling_llm({dummy_func}, max_tool_calls=10)
        node_cls = builder.build()
        assert dummy_function_node().node_type in node_cls.tool_nodes()
        assert node_cls.max_tool_calls == 10
        assert isinstance(node_cls.get_llm(), type(llm_model()))
        assert node_cls.system_message().content == "sysmsg"
        assert node_cls.system_message().role == "system"

def test_nodebuilder_tool_calling_llm_with_function_node():
        builder = NodeBuilder(DummyToolCallNode)
        builder.llm_base(llm_model(), system_message=SystemMessage(content="sysmsg"))
        builder.tool_calling_llm({dummy_function_node()}, max_tool_calls=10)
        node_cls = builder.build()
        assert dummy_function_node().node_type in node_cls.tool_nodes()
        assert node_cls.max_tool_calls == 10
        assert isinstance(node_cls.get_llm(), type(llm_model()))
        assert node_cls.system_message().content == "sysmsg"
        assert node_cls.system_message().role == "system"

def test_nodebuilder_setup_function_node():
    builder = NodeBuilder(SyncDynamicFunctionNode, name="FuncNode")
    builder.setup_function_node(dummy_func, tool_details=dummy_manifest().description, tool_params=dummy_manifest().parameters)
    node_cls = builder.build()
    assert issubclass(node_cls, SyncDynamicFunctionNode)
    assert node_cls.name() == "FuncNode"
    assert node_cls.func(5) == 5
    assert node_cls.tool_info().detail == dummy_manifest().description
    assert node_cls.tool_info().parameters[0].name == dummy_manifest().parameters[0].name

def test_nodebuilder_tool_callable_llm():
    builder = NodeBuilder(DummyNode, name="LLMNode")

    params = {dummy_manifest().parameters[0]}
    builder.tool_callable_llm(tool_details=dummy_manifest().description, tool_params=params)
    node_cls = builder.build()
    assert hasattr(node_cls, "tool_info")
    assert hasattr(node_cls, "prepare_tool")
    assert node_cls.tool_info().detail == dummy_manifest().description
    assert node_cls.tool_info().parameters == params

def test_nodebuilder_override_tool_info_with_tool():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.tool_callable_llm(tool_details=dummy_manifest().description, tool_params={dummy_manifest().parameters[0]})
    tool_obj = Tool(name="tool_obj", detail="", parameters=None)
    builder.override_tool_info(tool=tool_obj)
    node_cls = builder.build()
    assert isinstance(node_cls.tool_info(), Tool)
    assert node_cls.tool_info().name == "tool_obj"
    builder2 = NodeBuilder(DummyNode, name="TestNode")
    params = {Parameter(name="x", param_type="integer", description="desc")}
    builder2.override_tool_info(tool_details="details", tool_params=params)
    node_cls2 = builder2.build()
    assert hasattr(node_cls2, "tool_info")
    assert node_cls2.tool_info().detail == "details"
    assert node_cls2.tool_info().parameters == params

def test_nodebuilder_override_tool_info_with_parameters():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.override_tool_info(name="tool_obj")
    node_cls = builder.build()
    assert isinstance(node_cls.tool_info(), Tool)
    assert node_cls.tool_info().name == "tool_obj"
    builder2 = NodeBuilder(DummyNode, name="TestNode")
    params = {Parameter(name="x", param_type="integer", description="desc")}
    builder2.override_tool_info(tool_details="details", tool_params=params)
    node_cls2 = builder2.build()
    assert hasattr(node_cls2, "tool_info")
    assert node_cls2.tool_info().detail == "details"
    assert node_cls2.tool_info().parameters == params

def test_nodebuilder_add_attribute_override_warning():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.add_attribute("my_attr", 42, make_function=False)
    # Should warn on override
    with patch("warnings.warn") as warn_mock:
        builder.add_attribute("my_attr", 99, make_function=False)
        warn_mock.assert_called_once()

def test_nodebuilder_wrong_base_class_error():
    class NotNode: pass
    with pytest.raises(AssertionError):
        NodeBuilder(NotNode, name="BadNode").llm_base(llm="mock_llm")

def test_nodebuilder_duplicate_param_names_error():
    builder = NodeBuilder(DummyNode, name="LLMNode")
    with pytest.raises(NodeCreationError):
        builder.tool_callable_llm(tool_details="details", tool_params=[Parameter(name="x", param_type="integer", description="desc"), Parameter(name="x", param_type="integer", description="desc")])

def test_nodebuilder_negative_max_tool_calls_error():
        builder = NodeBuilder(DummyToolCallNode, name="ToolNode")
        builder.llm_base(llm_model(), system_message=SystemMessage(content="sysmsg"))
        with pytest.raises(NodeCreationError):
            builder.tool_calling_llm({dummy_func}, max_tool_calls=-1)

def test_nodebuilder_override_tool_info_conflict():
    builder = NodeBuilder(DummyNode, name="TestNode")
    with pytest.raises(AssertionError):
        builder.override_tool_info(tool=Tool(name="tool_obj", detail="", parameters=None), name="conflict", tool_details="details", tool_params={Parameter(name="x", param_type="integer", description="desc")})

def test_nodebuilder_add_attribute_callable_field():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.add_attribute("callable_field", lambda: 123, make_function=False)
    node_cls = builder.build()
    assert node_cls.callable_field == 123

def test_nodebuilder_add_attribute_non_callable_field():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.add_attribute("non_callable_field", 456, make_function=False)
    node_cls = builder.build()
    assert node_cls.non_callable_field == 456

def test_nodebuilder_add_attribute_callable_method():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.add_attribute("callable_method", lambda cls: 789, make_function=True)
    node_cls = builder.build()
    assert node_cls.callable_method() == 789

def test_nodebuilder_add_attribute_non_callable_method():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.add_attribute("non_callable_method", 101112, make_function=True)
    node_cls = builder.build()
    assert node_cls.non_callable_method() == 101112

def test_nodebuilder_tool_callable_llm_wrong_base():
    class NotLLM(Node):
        @classmethod
        def name(cls): return "NotLLM"
        async def invoke(self): return "notllm"
        @classmethod
        def type(cls): return "Tool"
    builder = NodeBuilder(NotLLM, name="NotLLM")
    with pytest.raises(AssertionError):
        builder.tool_callable_llm(tool_details="details", tool_params={Parameter(name="x", param_type="integer", description="desc")})

def test_nodebuilder_add_attribute_make_function_with_non_callable():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.add_attribute("non_callable_func", 123, make_function=True)
    node_cls = builder.build()
    assert node_cls.non_callable_func() == 123

def test_nodebuilder_llm_base_with_none():
    builder = NodeBuilder(DummyNode, name="LLMNode")
    builder.llm_base(llm=None, system_message=None)
    node_cls = builder.build()
    assert node_cls.get_llm() is None
    assert node_cls.system_message() is None

def test_nodebuilder_override_tool_info_with_only_name():
    builder = NodeBuilder(DummyNode, name="TestNode")
    node_cls = builder.build()
    builder.override_tool_info(name="tool_name")
    node_cls2 = builder.build()
    assert hasattr(node_cls2, "tool_info")

def test_nodebuilder_add_attribute_override_warning_make_function():
    builder = NodeBuilder(DummyNode, name="TestNode")
    builder.add_attribute("my_method", lambda cls: 1, make_function=True)
    with patch("warnings.warn") as warn_mock:
        builder.add_attribute("my_method", lambda cls: 2, make_function=True)
        warn_mock.assert_called_once()

def test_nodebuilder_setup_function_node_wrong_base():
    class NotFunctionNode(Node):
        @classmethod
        def name(cls): return "NotFunctionNode"
        async def invoke(self): return "notfunc"
        @classmethod
        def type(cls): return "Tool"
    builder = NodeBuilder(NotFunctionNode, name="NotFunctionNode")
    with pytest.raises(AssertionError):
        builder.setup_function_node(dummy_func)

def test_classmethod_preserving_function_meta():
    def f(x): return x + 1
    cm = classmethod_preserving_function_meta(f)
    class Dummy(Node):
        @classmethod
        def name(cls): return "Dummy"
        async def invoke(self): return "dummy"
        @classmethod
        def type(cls): return "Tool"
    Dummy.f = cm
    assert Dummy.f(2) == 3
