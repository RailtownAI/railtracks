"""Unit tests for gaps in built_nodes/llm/llm_helpers.py: `get_node_from_name`'s
multiple-candidates path, and `llm_prepare_called_as_tool_factory`'s array/object
formatting branches (previously only exercised indirectly, with string params).
"""

from __future__ import annotations

import pytest
import railtracks.built_nodes.llm.llm_helpers as llm_helpers
from railtracks.built_nodes.llm.llm_helpers import (
    get_node_from_name,
    llm_prepare_called_as_tool_factory,
)
from railtracks.exceptions import LLMError, NodeInvocationError
from railtracks.llm import Parameter
from railtracks.llm.tools.tool import Tool, ToolCreationError


def _fake_tool_node(name: str):
    class _FakeToolNode:
        @classmethod
        def tool_info(cls) -> Tool:
            return Tool(name=name, detail="a fake tool", parameters=[])

    return _FakeToolNode


# ---------------------------------------------------------------------------
# get_node_from_name
# ---------------------------------------------------------------------------


def test_get_node_from_name_returns_the_matching_node():
    node_a = _fake_tool_node("a")
    node_b = _fake_tool_node("b")

    result = get_node_from_name("b", [node_a, node_b])

    assert result is node_b


def test_get_node_from_name_raises_runtime_error_when_not_found():
    node_a = _fake_tool_node("a")

    with pytest.raises(RuntimeError, match="not found"):
        get_node_from_name("missing", [node_a])


def test_get_node_from_name_raises_on_duplicate_candidate_names():
    """Two tool nodes registered under the same name is a mis-configuration the
    caller should never hit -- pinned down here as a defensive assertion."""
    node_a = _fake_tool_node("dup")
    node_b = _fake_tool_node("dup")

    with pytest.raises(AssertionError, match="Multiple tool nodes found"):
        get_node_from_name("dup", [node_a, node_b])


# ---------------------------------------------------------------------------
# llm_prepare_called_as_tool_factory
# ---------------------------------------------------------------------------


def test_prepare_called_as_tool_formats_array_param_with_list_value():
    params = [Parameter(name="items", param_type="array", description="d")]
    prepare = llm_prepare_called_as_tool_factory(params)

    history = prepare(items=[1, 2, 3])

    assert "items: 1, 2, 3" in history[0].content


def test_prepare_called_as_tool_formats_object_param_with_dict_value():
    params = [Parameter(name="config", param_type="object", description="d")]
    prepare = llm_prepare_called_as_tool_factory(params)

    history = prepare(config={"a": 1, "b": 2})

    assert "config: a=1; b=2" in history[0].content


def test_prepare_called_as_tool_formats_string_param_plainly():
    params = [Parameter(name="x", param_type="string", description="d")]
    prepare = llm_prepare_called_as_tool_factory(params)

    history = prepare(x="hello")

    assert "x: hello" in history[0].content


def test_prepare_called_as_tool_empty_kwargs_returns_empty_history():
    params = [Parameter(name="x", param_type="string", description="d")]
    prepare = llm_prepare_called_as_tool_factory(params)

    history = prepare()

    assert list(history) == []


# ---------------------------------------------------------------------------
# llm_invoke_factory error translation
# ---------------------------------------------------------------------------
async def test_tool_creation_error_becomes_a_fatal_node_invocation_error(monkeypatch):
    """`ToolCreationError` is raised inside the llm package (which cannot import
    railtracks' errors), so the agent layer translates it back into the fatal
    `NodeInvocationError` callers rely on rather than masking it as an `LLMError`."""

    class _ExplodingInvoker:
        @classmethod
        def create_with_llm_observe(cls, *args, **kwargs):
            return cls()

        async def invoke(self, *args, **kwargs):
            raise ToolCreationError(
                message="Unable to parse Tool.parameters. It was 123",
                notes=["Tool.parameters must be a set of Parameter objects"],
            )

    monkeypatch.setattr(llm_helpers, "ModelInvoker", _ExplodingInvoker)

    class _FakeNode:
        _user_model_middleware = []
        _scope_manager = None

    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(NodeInvocationError) as exc:
        await invoke(_FakeNode(), "hello")

    assert exc.value.fatal is True
    assert not isinstance(exc.value, LLMError)
    assert "Unable to parse Tool.parameters" in str(exc.value)
    assert exc.value.notes == ["Tool.parameters must be a set of Parameter objects"]
