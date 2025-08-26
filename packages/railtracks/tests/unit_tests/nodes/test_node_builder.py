import pytest
from railtracks.built_nodes._node_builder import NodeBuilder
from unittest.mock import patch
# ================= START NodeBuilder tests ============

def test_add_attribute_non_function_sets_value(dummy_node_class):
    builder = NodeBuilder(dummy_node_class)
    builder.add_attribute("my_attr", 42, make_function=False)
    klass = builder.build()
    assert hasattr(klass, "my_attr")
    assert klass.my_attr == 42

def test_add_attribute_function_sets_classmethod(dummy_node_class):
    def cm(cls):
        return "hello"
    builder = NodeBuilder(dummy_node_class)
    builder.add_attribute("greet", cm, make_function=True)
    klass = builder.build()
    assert klass.greet() == "hello"

def test_override_existing_method_warns(dummy_node_class):
    builder = NodeBuilder(dummy_node_class)
    builder.add_attribute("foo", 1, make_function=False)
    with pytest.warns(UserWarning):
        builder.add_attribute("foo", 2, make_function=False)
    klass = builder.build()
    assert klass.foo == 2

def test_build_class_has_correct_name(dummy_node_class):
    builder = NodeBuilder(dummy_node_class, class_name="MyCustomNode")
    klass = builder.build()
    assert klass.__name__ == "MyCustomNode"

def test_build_class_default_name(dummy_node_class):
    builder = NodeBuilder(dummy_node_class)
    klass = builder.build()
    assert klass.__name__.startswith("Dynamic")

def test_init_with_name_and_return_into(dummy_node_class):
    builder = NodeBuilder(dummy_node_class, name="PrettyName", return_into="zz")
    klass = builder.build()
    assert klass.name() == "PrettyName"
    assert klass.return_into() == "zz"

def test_llm_base_overrides_model_and_system_message(patch_llm_base, dummy_system_message):
    builder = NodeBuilder(patch_llm_base)
    builder.llm_base(llm_model="MODEL", system_message=dummy_system_message)
    klass = builder.build()
    # The 'get_llm_model' and 'system_message' should be set as class methods
    assert klass.get_llm_model() == "MODEL"
    assert klass.system_message().content == "DummySystemMessage"

def test_structured_sets_output_schema(dummy_node_class):
    class DummySchema: pass
    builder = NodeBuilder(dummy_node_class)
    builder.structured(schema=DummySchema)
    klass = builder.build()
    assert klass.output_schema() is DummySchema

def test_tool_calling_llm_sets_tool_nodes_and_max(
    patch_outputless_toolcall_llm, patch_node, monkeypatch
):
    # Patch function_node to identity function returning .node_type attribute or input type
    monkeypatch.setattr("railtracks.built_nodes._node_builder.isfunction", lambda obj: False)
    builder = NodeBuilder(patch_outputless_toolcall_llm)
    builder.tool_calling_llm(
        connected_nodes={patch_node}, max_tool_calls=5,
    )
    klass = builder.build()
    assert klass.tool_nodes() == {patch_node}
    assert klass.max_tool_calls == 5

def test_chat_ui_sets_and_starts_server(dummy_node_class, dummy_chat_ui):
    builder = NodeBuilder(dummy_node_class)
    builder.chat_ui(dummy_chat_ui)
    klass = builder.build()
    assert klass.chat_ui.started is True

def test_setup_function_node_sets_func_and_type_mapper(patch_function_node, dummy_tool, dummy_parameter, monkeypatch):
    monkeypatch.setattr("railtracks.built_nodes._node_builder.TypeMapper", lambda func: f"TM({func.__name__})")
    monkeypatch.setattr("railtracks.built_nodes._node_builder.Tool", dummy_tool)
    def example_func(x): return x + 1
    builder = NodeBuilder(patch_function_node)
    builder.setup_function_node(example_func, tool_details="desc", tool_params=[dummy_parameter])
    klass = builder.build()
    assert klass.type_mapper() == "TM(example_func)"
    # 'func' should be unbound function
    assert klass.func(5) == 6
    # tool_info returns DummyTool, which is tuple
    tool_info = klass.tool_info()
    assert tool_info[1] == "desc"

@pytest.mark.skip(reason="Finsih Later")
def test_tool_callable_llm_sets_tool_info_and_prepare_tool(
    patch_llm_base,
    dummy_parameter,
    monkeypatch
):
    monkeypatch.setattr("railtracks.built_nodes._node_builder._check_tool_params_and_details", lambda p, d: None)
    monkeypatch.setattr("railtracks.built_nodes._node_builder._check_duplicate_param_names", lambda params: None)
    builder = NodeBuilder(patch_llm_base, name="DummyBuilder")
    builder.tool_callable_llm(tool_details="detX", tool_params={dummy_parameter})
    klass = builder.build()
    tool = klass.tool_info()
    assert tool.detail == "detX"
    # prepare_tool creates a new DummyLLMBase with message history string
    inst = klass.prepare_tool({"foo": "bar"})
    assert isinstance(inst, patch_llm_base)
    assert inst == "history-{'foo': 'bar'}-{" + "'paramA'" + "}"

def test_override_tool_info_with_tool_object(dummy_node_class, dummy_tool):
    builder = NodeBuilder(dummy_node_class)
    builder.override_tool_info(tool=dummy_tool)
    klass = builder.build()
    assert klass.tool_info() == dummy_tool

def test_override_tool_info_with_details_and_params(dummy_node_class, dummy_parameter):
    builder = NodeBuilder(dummy_node_class)
    params = {dummy_parameter}
    builder.override_tool_info(name="Boo", tool_details="abc", tool_params=params)
    klass = builder.build()
    result = klass.tool_info()
    assert result.detail == "abc"
    assert result.name == "Boo"
    assert result.parameters == params

# ================ END NodeBuilder tests ===============