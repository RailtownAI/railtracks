"""Unit tests for gaps in built_nodes/llm/llm_helpers.py: `get_node_from_name`'s
multiple-candidates path, and `llm_prepare_called_as_tool_factory`'s array/object
formatting branches (previously only exercised indirectly, with string params).
"""

from __future__ import annotations

import pytest
from railtracks.built_nodes.llm.llm_helpers import (
    get_node_from_name,
    llm_prepare_called_as_tool_factory,
)
from railtracks.llm import Parameter
from railtracks.llm.tools.tool import Tool


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
