"""Unit tests for gaps in built_nodes/llm/llm_helpers.py: `get_node_from_name`'s
multiple-candidates path, and `llm_prepare_called_as_tool_factory`'s array/object
formatting branches (previously only exercised indirectly, with string params).
"""

from __future__ import annotations

import litellm
import pytest
import railtracks.built_nodes.llm.llm_helpers as llm_helpers
from railtracks.built_nodes.llm.llm_helpers import (
    get_node_from_name,
    llm_prepare_called_as_tool_factory,
)
from railtracks.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    NodeInvocationError,
)
from railtracks.llm import Parameter
from railtracks.llm._exceptions import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    RetryError,
)
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import UserMessage
from railtracks.llm.models._model_exception_base import ModelError, ModelNotFoundError
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
def _invoker_raising(exc: Exception):
    """A stand-in ModelInvoker whose `invoke` always raises `exc`."""

    class _ExplodingInvoker:
        @classmethod
        def create_with_llm_observe(cls, *args, **kwargs):
            return cls()

        async def invoke(self, *args, **kwargs):
            raise exc

    return _ExplodingInvoker


class _FakeNode:
    _user_model_middleware = []
    _scope_manager = None


async def test_tool_creation_error_becomes_a_fatal_node_invocation_error(monkeypatch):
    """A malformed tool ends the run, rather than being masked as an `LLMError`."""
    inner = ToolCreationError(
        message="Unable to parse Tool.parameters. It was 123",
        notes=["Tool.parameters must be a set of Parameter objects"],
    )
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_raising(inner))

    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(NodeInvocationError) as exc:
        await invoke(_FakeNode(), "hello")

    assert exc.value.fatal is True
    assert not isinstance(exc.value, LLMError)
    assert "Unable to parse Tool.parameters" in str(exc.value)
    assert exc.value.notes == ["Tool.parameters must be a set of Parameter objects"]


async def test_provider_error_is_translated_into_llmerror(monkeypatch):
    """A `ProviderError` surfaces from a node as the node-terminating `LLMError`."""
    inner = ModelError(reason="Structured LLM call failed")
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_raising(inner))

    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(LLMError) as exc:
        await invoke(_FakeNode(), "hello")

    # Both dispatch axes answerable from the one object.
    assert isinstance(exc.value, NodeInvocationError)
    assert isinstance(exc.value, LLMError)
    assert exc.value.reason == "Structured LLM call failed"
    assert "ModelError(" not in str(exc.value)
    assert exc.value.__cause__ is inner


async def test_unexpected_exception_keeps_its_cause(monkeypatch):
    """Even the catch-all branch chains, so `__cause__` is never dropped."""
    inner = ValueError("connection reset")
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_raising(inner))

    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(LLMError) as exc:
        await invoke(_FakeNode(), "hello")

    assert exc.value.__cause__ is inner


async def test_existing_llmerror_is_not_wrapped_twice(monkeypatch):
    """An already-classified error passes through with its `message_history` intact."""
    history = MessageHistory([UserMessage("hi")])
    inner = LLMError(reason="stream ended early", message_history=history)
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_raising(inner))

    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(LLMError) as exc:
        await invoke(_FakeNode(), "hello")

    assert exc.value is inner
    assert exc.value.message_history is history
    assert exc.value.reason == "stream ended early"


# ---------------------------------------------------------------------------
# Provider failure classification
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "provider_error,expected",
    [
        (ProviderTimeoutError("timed out"), LLMTimeoutError),
        (ProviderRateLimitError("slow down"), LLMRateLimitError),
        (ProviderAuthenticationError("bad key"), LLMAuthenticationError),
        (ModelError(reason="something else"), LLMError),
    ],
    ids=["timeout", "rate_limit", "auth", "unclassified"],
)
async def test_provider_failures_map_to_llmerror_subclasses(
    monkeypatch, provider_error, expected
):
    """Users branch with plain `except` clauses; the boundary picks the class."""
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_raising(provider_error))
    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(expected) as exc:
        await invoke(_FakeNode(), "hello")

    assert type(exc.value) is expected
    # Every subclass stays catchable by the broader clauses above it.
    assert isinstance(exc.value, LLMError)
    assert isinstance(exc.value, NodeInvocationError)
    assert exc.value.__cause__ is provider_error


async def test_timeout_subclass_does_not_shadow_plain_llmerror(monkeypatch):
    """`except LLMError` must still catch a timeout -- specificity is opt-in."""
    monkeypatch.setattr(
        llm_helpers, "ModelInvoker", _invoker_raising(ProviderTimeoutError("timed out"))
    )
    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(LLMError):
        await invoke(_FakeNode(), "hello")


async def test_exhausted_retry_of_timeouts_still_surfaces_as_a_timeout(monkeypatch):
    """A `RetryError` wrapping timeouts still reaches the caller as `LLMTimeoutError`."""
    retry_error = RetryError(
        "exponential",
        "Max retries exceeded",
        [],
        [litellm.exceptions.Timeout("t", "m", "p")],
    )
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_raising(retry_error))
    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(LLMTimeoutError) as exc:
        await invoke(_FakeNode(), "hello")

    # RetryError itself is preserved as the cause, so "we retried" is still recoverable.
    assert exc.value.__cause__ is retry_error
    assert retry_error.exception_list


async def test_tool_creation_error_debug_tips_are_rendered_once(monkeypatch):
    """The translated error re-renders the tips; the raw message must go across, not
    `str(inner)`, which already carries a rendered block of its own."""
    note = "Tool.parameters must be a set of Parameter objects"
    inner = ToolCreationError(message="Unable to parse Tool.parameters", notes=[note])
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_raising(inner))

    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(NodeInvocationError) as exc:
        await invoke(_FakeNode(), "hello")

    rendered = str(exc.value)
    assert rendered.count("Tips to debug") == 1
    assert rendered.count(note) == 1
    # Translating must not change how the failure presents: an already-rendered
    # inner message would nest a second block inside a reset colour code.
    assert rendered == str(
        NodeInvocationError(
            message="Unable to parse Tool.parameters", notes=[note], fatal=True
        )
    )


@pytest.mark.parametrize(
    "provider_error",
    [
        ModelNotFoundError(reason="no such model", notes=["Check the model name"]),
        RetryError("exponential", "Max retries exceeded", ["Check the model name"], []),
    ],
    ids=["model_not_found", "retry_error"],
)
async def test_provider_error_notes_survive_translation(monkeypatch, provider_error):
    """Debugging tips attached by the llm layer are worth as much on the node side."""
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_raising(provider_error))
    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(LLMError) as exc:
        await invoke(_FakeNode(), "hello")

    assert exc.value.notes == ["Check the model name"]
    assert "Check the model name" in str(exc.value)


@pytest.mark.parametrize(
    "raw_error,expected",
    [
        (litellm.exceptions.Timeout("t", "m", "p"), LLMTimeoutError),
        (
            litellm.exceptions.RateLimitError("slow down", "m", "p"),
            LLMRateLimitError,
        ),
        (
            litellm.exceptions.AuthenticationError("bad key", "m", "p"),
            LLMAuthenticationError,
        ),
        (ValueError("connection reset"), LLMError),
    ],
    ids=["timeout", "rate_limit", "auth", "unrelated"],
)
async def test_raw_provider_exceptions_are_classified_too(
    monkeypatch, raw_error, expected
):
    """Not every provider failure passes through `_call_provider` -- one raised part
    way through a stream reaches the boundary raw, and must still classify."""
    monkeypatch.setattr(llm_helpers, "ModelInvoker", _invoker_raising(raw_error))
    invoke = llm_helpers.llm_invoke_factory(object(), None)

    with pytest.raises(expected) as exc:
        await invoke(_FakeNode(), "hello")

    assert type(exc.value) is expected
    assert exc.value.__cause__ is raw_error
