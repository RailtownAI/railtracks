"""Tests for ModelInvoker's LLM-call scoping (llm_call_id)."""

import pytest

import railtracks.context.central as central
from railtracks.built_nodes.llm.middleware.wrap_llm import wrap_llm
from railtracks.built_nodes.llm.model_invoker import ModelInvoker
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message, Role
from railtracks.llm.response import Response
from railtracks.utils.config import ExecutorConfig


class _FakeModel:
    def chat(self, messages):
        return Response(message=Message(role=Role.assistant, content="hi"))


@pytest.fixture(autouse=True)
def cleanup_globals():
    central.delete_globals()
    yield
    central.delete_globals()


def _register():
    central.register_globals(
        session_id="s1",
        rt_publisher=None,
        executor_config=ExecutorConfig(),
        global_context_vars={},
    )


async def test_invoke_scopes_llm_call_id_for_middleware_and_reverts_after():
    _register()
    captured = []

    @wrap_llm
    async def capture(call, message_history, schema, tools):
        captured.append(central.get_llm_call_id())
        return await call(message_history, schema, tools)

    invoker = ModelInvoker(
        _FakeModel(), [capture], get_scope_manager=central.ContextVarScopeManager
    )

    assert central.get_llm_call_id() is None
    await invoker.invoke(MessageHistory())
    assert central.get_llm_call_id() is None

    assert captured == [captured[0]]
    assert captured[0] is not None


async def test_invoke_generates_a_fresh_llm_call_id_each_call():
    _register()
    captured = []

    @wrap_llm
    async def capture(call, message_history, schema, tools):
        captured.append(central.get_llm_call_id())
        return await call(message_history, schema, tools)

    invoker = ModelInvoker(
        _FakeModel(), [capture], get_scope_manager=central.ContextVarScopeManager
    )

    await invoker.invoke(MessageHistory())
    await invoker.invoke(MessageHistory())

    assert len(captured) == 2
    assert captured[0] != captured[1]
