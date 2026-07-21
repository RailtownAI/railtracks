import asyncio
from unittest.mock import MagicMock

import pytest
import railtracks as rt
from pydantic import BaseModel
from railtracks.built_nodes._node_builder import (
    classmethod_preserving_function_meta,
    safe_create_node,
)
from railtracks.built_nodes.function.node_builder import FunctionNodeBuilder
from railtracks.built_nodes.llm.middleware import after_llm
from railtracks.built_nodes.llm.node_builder import LLMNodeBuilder
from railtracks.exceptions.errors import NodeCreationError
from railtracks.guardrails.core import GuardrailDecision, InputGuard, OutputGuard
from railtracks.llm import Message, MessageHistory, Parameter, SystemMessage
from railtracks.llm.message import AssistantMessage, Role
from railtracks.llm.response import Response
from railtracks.middleware import wrap_node
from railtracks.nodes.nodes import Node


class Schema(BaseModel):
    x: int


def dummy_model():
    return MagicMock()


async def async_func(x: int) -> int:
    return x


# --- LLMNodeBuilder.llm ---

def test_nodebuilder_llm_basic_build():
    node_cls = LLMNodeBuilder.llm("TestNode", model=dummy_model()).build()
    assert issubclass(node_cls, Node)
    assert node_cls.name() == "TestNode"
    assert node_cls.type() == "Agent"


def test_nodebuilder_llm_default_class_name():
    node_cls = LLMNodeBuilder.llm("MyLLM", model=dummy_model()).build()
    assert node_cls.__name__ == "MyLLMNode"


def test_nodebuilder_llm_custom_class_name():
    node_cls = LLMNodeBuilder.llm("MyLLM", class_name="Custom", model=dummy_model()).build()
    assert node_cls.__name__ == "CustomNode"


def test_nodebuilder_llm_has_invoke():
    node_cls = LLMNodeBuilder.llm("TestNode", model=dummy_model()).build()
    assert hasattr(node_cls, "invoke")



def test_nodebuilder_llm_with_tool_details_has_tool_info():
    params = [Parameter(name="x", description="Input", param_type="integer")]
    node_cls = LLMNodeBuilder.llm(
        "TestNode",
        model=dummy_model(),
        tool_details="Does something",
        tool_params=params,
    ).build()
    assert hasattr(node_cls, "tool_info")
    tool = node_cls.tool_info()
    assert tool.detail == "Does something"
    assert tool.name == "TestNode"


def test_nodebuilder_llm_with_tool_details_has_prepare_args():
    params = [Parameter(name="x", description="Input", param_type="integer")]
    node_cls = LLMNodeBuilder.llm(
        "TestNode",
        model=dummy_model(),
        tool_details="Does something",
        tool_params=params,
    ).build()
    assert hasattr(node_cls, "prepare_args")


def test_nodebuilder_llm_with_system_message_string():
    node_cls = LLMNodeBuilder.llm(
        "TestNode",
        model=dummy_model(),
        system_message=SystemMessage(content="sysmsg"),
    ).build()
    assert issubclass(node_cls, Node)


def test_nodebuilder_llm_with_schema():
    node_cls = LLMNodeBuilder.llm(
        "TestNode",
        model=dummy_model(),
        schema=Schema,
    ).build()
    assert issubclass(node_cls, Node)


def test_nodebuilder_llm_duplicate_param_names_error():
    params = [
        Parameter(name="x", param_type="integer", description="desc"),
        Parameter(name="x", param_type="integer", description="desc"),
    ]
    with pytest.raises(NodeCreationError):
        LLMNodeBuilder.llm(
            "TestNode",
            model=dummy_model(),
            tool_details="details",
            tool_params=params,
        )


# --- NodeBuilder.function ---

def test_nodebuilder_function_basic_build():
    node_cls = FunctionNodeBuilder.function(async_func).build()
    assert issubclass(node_cls, Node)
    assert node_cls.name() == "async_func"
    assert node_cls.type() == "Tool"


def test_nodebuilder_function_default_class_name():
    node_cls = FunctionNodeBuilder.function(async_func).build()
    assert node_cls.__name__ == "Async_funcNode"


def test_nodebuilder_function_custom_name():
    node_cls = FunctionNodeBuilder.function(async_func, name="MyFunc").build()
    assert node_cls.name() == "MyFunc"


def test_nodebuilder_function_custom_class_name():
    node_cls = FunctionNodeBuilder.function(async_func, class_name="MyClass").build()
    assert node_cls.__name__ == "MyClassNode"


def test_nodebuilder_function_has_tool_info():
    node_cls = FunctionNodeBuilder.function(async_func).build()
    assert hasattr(node_cls, "tool_info")


def test_nodebuilder_function_tool_info_detail():
    params = [Parameter(name="x", param_type="integer", description="Input")]
    node_cls = FunctionNodeBuilder.function(
        async_func,
        tool_details="Does a thing",
        tool_params=params,
    ).build()
    assert node_cls.tool_info().detail == "Does a thing"


def test_nodebuilder_function_invoke_calls_func():
    node_cls = FunctionNodeBuilder.function(async_func).build()
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


# --- middleware / guardrails / context injection wiring ---


def test_nodebuilder_function_middleware_sets_user_middleware():
    @wrap_node
    async def tag(call, *args, **kwargs):
        return await call(*args, **kwargs)

    node_cls = FunctionNodeBuilder.function(async_func, middleware=[tag]).build()
    assert node_cls._user_middleware == [tag]


def test_nodebuilder_llm_middleware_sets_user_middleware(mock_llm):
    # LLMNodeBuilder.llm deep-copies `middleware` before storing it, so the stored
    # Middleware objects are copies (not identical by `==`) -- assert functionally.
    fired = {"value": False}

    @wrap_node
    async def tag(call, *args, **kwargs):
        fired["value"] = True
        return await call(*args, **kwargs)

    node_cls = LLMNodeBuilder.llm(
        "TestNode", model=mock_llm(custom_response="hi"), middleware=[tag]
    ).build()

    async def top():
        with rt.Session():
            return await rt.call(node_cls, user_input="hello")

    asyncio.run(top())
    assert fired["value"]
    assert len(node_cls._user_middleware) == 1


def test_nodebuilder_llm_model_middleware_wraps_model_call(mock_llm):
    calls = []

    @wrap_node
    async def tracer(call, *args, **kwargs):
        calls.append("in")
        result = await call(*args, **kwargs)
        calls.append("out")
        return result

    node_cls = LLMNodeBuilder.llm(
        "TestNode", model=mock_llm(custom_response="hi"), model_middleware=[tracer]
    ).build()

    async def top():
        with rt.Session():
            return await rt.call(node_cls, user_input="hello")

    result = asyncio.run(top())
    assert result.content == "hi"
    assert calls == ["in", "out"]


def _echo_last_message(messages):
    return Response(message=Message(role=Role.assistant, content=messages[-1].content))


def test_nodebuilder_llm_context_injection_via_middleware(mock_llm):
    # Empty user_input -> the system message is the only (and therefore last) message,
    # so echoing messages[-1] reflects the (possibly context-injected) system content.
    model = mock_llm()
    model._chat = _echo_last_message

    node_cls = LLMNodeBuilder.llm(
        "CtxNode",
        model=model,
        system_message=SystemMessage(content="{secret}"),
        model_middleware=[rt.prebuilt.middleware.ContextInjection()],
    ).build()

    async def top():
        with rt.Session(context={"secret": "tomato"}):
            return await rt.call(node_cls, user_input=MessageHistory())

    assert asyncio.run(top()).content == "tomato"


def test_nodebuilder_llm_no_injection_by_default(mock_llm):
    # Injection is opt-in: without a ContextInjection entry the template is untouched.
    model = mock_llm()
    model._chat = _echo_last_message

    node_cls = LLMNodeBuilder.llm(
        "CtxNode",
        model=model,
        system_message=SystemMessage(content="{secret}"),
    ).build()

    async def top():
        with rt.Session(context={"secret": "tomato"}):
            return await rt.call(node_cls, user_input=MessageHistory())

    assert asyncio.run(top()).content == "{secret}"


def test_nodebuilder_llm_guardrails_input_and_output_both_fire(mock_llm):
    fired = {"input": False, "output": False}

    class MarkInputGuard(InputGuard):
        def __call__(self, event):
            fired["input"] = True
            return GuardrailDecision.allow(reason="ok")

    class MarkOutputGuard(OutputGuard):
        def __call__(self, event):
            fired["output"] = True
            return GuardrailDecision.allow(reason="ok")

    node_cls = LLMNodeBuilder.llm(
        "GuardedNode",
        model=mock_llm(custom_response="hi"),
        model_middleware=[MarkInputGuard(), MarkOutputGuard()],
    ).build()

    async def top():
        with rt.Session():
            return await rt.call(node_cls, "hello")

    asyncio.run(top())
    assert fired == {"input": True, "output": True}


def test_nodebuilder_llm_guardrails_input_only_does_not_fire_output(mock_llm):
    fired = {"input": False}

    class MarkInputGuard(InputGuard):
        def __call__(self, event):
            fired["input"] = True
            return GuardrailDecision.allow(reason="ok")

    node_cls = LLMNodeBuilder.llm(
        "GuardedInputOnlyNode",
        model=mock_llm(custom_response="hi"),
        model_middleware=[MarkInputGuard()],
    ).build()

    async def top():
        with rt.Session():
            return await rt.call(node_cls, "hello")

    result = asyncio.run(top())
    assert fired["input"]
    assert result.content == "hi"


def test_nodebuilder_llm_empty_model_middleware_is_a_no_op(mock_llm):
    node_cls = LLMNodeBuilder.llm(
        "EmptyGuardNode", model=mock_llm(custom_response="hi"), model_middleware=[]
    ).build()

    async def top():
        with rt.Session():
            return await rt.call(node_cls, "hello")

    assert asyncio.run(top()).content == "hi"


def test_nodebuilder_llm_guardrail_vs_user_middleware_order_is_list_position(
    mock_llm,
):
    """Guardrails have no special/fixed slot: whichever model_middleware entry is
    listed first is outermost and applies its transform last (i.e. wins), exactly
    like any other model_middleware. List position — not "guard vs. non-guard" —
    determines precedence.
    """

    class AlwaysRedactOutputGuard(OutputGuard):
        def __call__(self, event):
            return GuardrailDecision.transform_output(
                output_message=AssistantMessage("[REDACTED BY GUARDRAIL]"),
                reason="always redact",
            )

    @after_llm
    def overwrite_after_guardrail(response):
        return Response(
            message=AssistantMessage("overwritten by user middleware"),
            message_info=response.message_info,
        )

    guard_first_cls = LLMNodeBuilder.llm(
        "GuardFirstNode",
        model=mock_llm(custom_response="hello"),
        model_middleware=[AlwaysRedactOutputGuard(), overwrite_after_guardrail],
    ).build()

    user_first_cls = LLMNodeBuilder.llm(
        "UserFirstNode",
        model=mock_llm(custom_response="hello"),
        model_middleware=[overwrite_after_guardrail, AlwaysRedactOutputGuard()],
    ).build()

    async def top(node_cls):
        with rt.Session():
            return await rt.call(node_cls, user_input="hi")

    guard_first_result = asyncio.run(top(guard_first_cls))
    user_first_result = asyncio.run(top(user_first_cls))

    assert guard_first_result.content == "[REDACTED BY GUARDRAIL]"
    assert user_first_result.content == "overwritten by user middleware"


def test_nodebuilder_function_has_no_middleware_by_default():
    node_cls = FunctionNodeBuilder.function(async_func).build()
    assert node_cls._user_middleware == []
