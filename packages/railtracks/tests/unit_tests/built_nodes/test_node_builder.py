import asyncio

import pytest
from pydantic import BaseModel
from unittest.mock import MagicMock

from railtracks.built_nodes._node_builder import (
    NodeBuilder,
    classmethod_preserving_function_meta,
    safe_create_node,
)
from railtracks.built_nodes.llm_helpers import Gateway
from railtracks.exceptions.errors import NodeCreationError
from railtracks.llm import Parameter, SystemMessage
from railtracks.nodes.nodes import Node


class Schema(BaseModel):
    x: int


def dummy_gateway():
    return Gateway(model=MagicMock())


async def async_func(x: int) -> int:
    return x


# --- NodeBuilder.llm ---

def test_nodebuilder_llm_basic_build():
    node_cls = NodeBuilder.llm("TestNode", gateway=dummy_gateway()).build()
    assert issubclass(node_cls, Node)
    assert node_cls.name() == "TestNode"
    assert node_cls.type() == "Agent"


def test_nodebuilder_llm_default_class_name():
    node_cls = NodeBuilder.llm("MyLLM", gateway=dummy_gateway()).build()
    assert node_cls.__name__ == "MyLLMNode"


def test_nodebuilder_llm_custom_class_name():
    node_cls = NodeBuilder.llm("MyLLM", class_name="Custom", gateway=dummy_gateway()).build()
    assert node_cls.__name__ == "CustomNode"


def test_nodebuilder_llm_has_invoke():
    node_cls = NodeBuilder.llm("TestNode", gateway=dummy_gateway()).build()
    assert hasattr(node_cls, "invoke")


def test_nodebuilder_llm_no_tool_details_has_no_tool_info():
    node_cls = NodeBuilder.llm("TestNode", gateway=dummy_gateway()).build()
    assert not hasattr(node_cls, "tool_info")


def test_nodebuilder_llm_with_tool_details_has_tool_info():
    params = [Parameter(name="x", description="Input", param_type="integer")]
    node_cls = NodeBuilder.llm(
        "TestNode",
        gateway=dummy_gateway(),
        tool_details="Does something",
        tool_params=params,
    ).build()
    assert hasattr(node_cls, "tool_info")
    tool = node_cls.tool_info()
    assert tool.detail == "Does something"
    assert tool.name == "TestNode"


def test_nodebuilder_llm_with_tool_details_has_prepare_tool():
    params = [Parameter(name="x", description="Input", param_type="integer")]
    node_cls = NodeBuilder.llm(
        "TestNode",
        gateway=dummy_gateway(),
        tool_details="Does something",
        tool_params=params,
    ).build()
    assert hasattr(node_cls, "prepare_tool")


def test_nodebuilder_llm_with_system_message_string():
    node_cls = NodeBuilder.llm(
        "TestNode",
        gateway=dummy_gateway(),
        system_message=SystemMessage(content="sysmsg"),
    ).build()
    assert issubclass(node_cls, Node)


def test_nodebuilder_llm_with_schema():
    node_cls = NodeBuilder.llm(
        "TestNode",
        gateway=dummy_gateway(),
        schema=Schema,
    ).build()
    assert issubclass(node_cls, Node)


def test_nodebuilder_llm_duplicate_param_names_error():
    params = [
        Parameter(name="x", param_type="integer", description="desc"),
        Parameter(name="x", param_type="integer", description="desc"),
    ]
    with pytest.raises(NodeCreationError):
        NodeBuilder.llm(
            "TestNode",
            gateway=dummy_gateway(),
            tool_details="details",
            tool_params=params,
        )


# --- NodeBuilder.function ---

def test_nodebuilder_function_basic_build():
    node_cls = NodeBuilder.function(async_func).build()
    assert issubclass(node_cls, Node)
    assert node_cls.name() == "async_func"
    assert node_cls.type() == "Tool"


def test_nodebuilder_function_default_class_name():
    node_cls = NodeBuilder.function(async_func).build()
    assert node_cls.__name__ == "Async_funcNode"


def test_nodebuilder_function_custom_name():
    node_cls = NodeBuilder.function(async_func, name="MyFunc").build()
    assert node_cls.name() == "MyFunc"


def test_nodebuilder_function_custom_class_name():
    node_cls = NodeBuilder.function(async_func, class_name="MyClass").build()
    assert node_cls.__name__ == "MyClassNode"


def test_nodebuilder_function_has_tool_info():
    node_cls = NodeBuilder.function(async_func).build()
    assert hasattr(node_cls, "tool_info")


def test_nodebuilder_function_tool_info_detail():
    params = [Parameter(name="x", param_type="integer", description="Input")]
    node_cls = NodeBuilder.function(
        async_func,
        tool_details="Does a thing",
        tool_params=params,
    ).build()
    assert node_cls.tool_info().detail == "Does a thing"


def test_nodebuilder_function_invoke_calls_func():
    node_cls = NodeBuilder.function(async_func).build()
    result = asyncio.run(node_cls().invoke(5))
    assert result == 5


# --- safe_create_node ---

def test_safe_create_node_basic():
    async def invoke(self):
        return "ok"

    required = {
        "invoke": invoke,
        "name": classmethod_preserving_function_meta(lambda: "N"),
        "type": classmethod_preserving_function_meta(lambda: "Tool"),
    }
    node_cls = safe_create_node("TestClass", required, {})
    assert issubclass(node_cls, Node)
    assert node_cls.__name__ == "TestClassNode"


def test_safe_create_node_none_class_name_raises():
    with pytest.raises(ValueError):
        safe_create_node(None, {}, {})  # type: ignore[arg-type]


def test_safe_create_node_required_optional_name_collision_raises():
    with pytest.raises(ValueError):
        safe_create_node("Foo", {"shared": 1}, {"shared": 2})


def test_safe_create_node_optional_none_values_excluded():
    async def invoke(self):
        return "ok"

    required = {
        "invoke": invoke,
        "name": classmethod_preserving_function_meta(lambda: "N"),
        "type": classmethod_preserving_function_meta(lambda: "Tool"),
    }
    node_cls = safe_create_node("TestClass", required, {"missing_attr": None})
    assert not hasattr(node_cls, "missing_attr")


# --- classmethod_preserving_function_meta ---

def test_classmethod_preserving_function_meta():
    def f(x):
        return x + 1

    cm = classmethod_preserving_function_meta(f)

    class Dummy(Node):
        @classmethod
        def name(cls):
            return "Dummy"

        async def invoke(self):
            return "dummy"

        @classmethod
        def type(cls):
            return "Tool"

    Dummy.f = cm
    assert Dummy.f(2) == 3
