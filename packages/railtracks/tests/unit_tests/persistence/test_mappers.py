"""Pure-function tests for persistence mappers against hand-built domain objects."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from railtracks.llm import (
    AssistantMessage,
    MessageHistory,
    ToolCall,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from railtracks.persistence.mappers import (
    classify_message,
    jsonable,
    linked_node_to_rows,
    llm_details_to_call_row,
    output_kind_of,
    request_to_rows,
)
from railtracks.state.node import LinkedNode
from railtracks.state.request import Cancelled, Failure, RequestTemplate
from railtracks.utils.profiling import Stamp


def _stamp(step: int, time: float = 0.0, identifier: str = "s") -> Stamp:
    return Stamp(time=time, step=step, identifier=identifier)


class _FakeNode:
    """Duck-typed stand-in: mappers only call name() and type()."""

    uuid = "n-1"

    @classmethod
    def name(cls) -> str:
        return "FakeAgent"

    @classmethod
    def type(cls) -> str:
        return "Agent"


# ---------------------------------------------------------------- output_kind


def test_output_kind_of() -> None:
    assert output_kind_of(None) == "open"
    assert output_kind_of(Failure(ValueError("x"))) == "failure"
    assert output_kind_of(Cancelled()) == "cancelled"
    assert output_kind_of({"any": "thing"}) == "value"


# ------------------------------------------------------------------- jsonable


def test_jsonable_falls_back_like_the_json_format_did() -> None:
    class Opaque:
        def __str__(self) -> str:
            return "opaque-thing"

    encoded = jsonable({"x": Opaque()})
    assert isinstance(encoded["x"], str)
    assert "opaque-thing" in encoded["x"]


def test_jsonable_none_passthrough() -> None:
    assert jsonable(None) is None


# ----------------------------------------------------------- linked node rows


def test_linked_node_chain_unrolls_oldest_first() -> None:
    v1 = LinkedNode(identifier="n-1", stamp=_stamp(0, identifier="created"), parent=None, _node=_FakeNode())
    v2 = LinkedNode(identifier="n-1", stamp=_stamp(3, identifier="done"), parent=v1, _node=_FakeNode())

    node_row, versions = linked_node_to_rows(v2, run_id="r1")

    assert node_row.node_uuid == "n-1"
    assert node_row.name == "FakeAgent"
    assert node_row.node_type == "Agent"
    assert [v.stamp_step for v in versions] == [0, 3]
    assert [v.stamp_identifier for v in versions] == ["created", "done"]


# --------------------------------------------------------------- request rows


def _request_chain() -> RequestTemplate:
    created = RequestTemplate(
        identifier="req-1",
        source_id=None,
        sink_id="n-1",
        input=(("hello",), {"k": 1}),
        output=None,
        stamp=_stamp(0, time=10.0),
        parent=None,
    )
    return RequestTemplate(
        identifier="req-1",
        source_id=None,
        sink_id="n-1",
        input=created.input,
        output={"answer": 42},
        stamp=_stamp(5, time=15.0),
        parent=created,
    )


def test_request_row_carries_created_and_latest_stamps() -> None:
    row, failure = request_to_rows(_request_chain(), run_id="r1")

    assert failure is None
    assert row.created_stamp_step == 0
    assert row.created_stamp_time == 10.0
    assert row.stamp_step == 5
    assert row.stamp_time == 15.0
    assert row.status == "Completed"
    assert row.output_kind == "value"
    assert row.output_json == {"answer": 42}
    assert row.input_args_json == ["hello"]
    assert row.input_kwargs_json == {"k": 1}


def test_failed_request_emits_failure_row_not_output_json() -> None:
    failed = RequestTemplate(
        identifier="req-2",
        source_id="n-0",
        sink_id="n-1",
        input=((), {}),
        output=Failure(ValueError("boom")),
        stamp=_stamp(2),
        parent=None,
    )
    row, failure = request_to_rows(failed, run_id="r1")

    assert row.output_kind == "failure"
    assert row.status == "Failed"
    assert row.output_json is None
    assert failure is not None
    assert failure.request_id == "req-2"
    assert failure.exception_type == "ValueError"
    assert failure.message == "boom"


# ---------------------------------------------------------------- llm details


def test_llm_details_to_call_row() -> None:
    details = SimpleNamespace(
        input=MessageHistory([UserMessage("hi")]),
        output=AssistantMessage("hello"),
        model_name="gpt-4o",
        model_provider="openai",
        input_tokens=10,
        output_tokens=5,
        total_cost=0.001,
        system_fingerprint="fp",
        latency=0.4,
    )
    row = llm_details_to_call_row(
        details, node_uuid="n-1", session_id="s-1", call_index=2
    )
    assert row.model_name == "gpt-4o"
    assert row.call_index == 2
    assert row.input_tokens == 10
    assert row.total_cost == 0.001


# ------------------------------------------------------------ message classify


def test_classify_text_message() -> None:
    kind, text, content_json, tool_calls, tool_response = classify_message(
        UserMessage("hello world")
    )
    assert (kind, text, content_json) == ("text", "hello world", None)
    assert tool_calls == [] and tool_response is None


def test_classify_tool_calls_message() -> None:
    calls = [
        ToolCall(identifier="t1", name="search", arguments={"q": "x"}),
        ToolCall(identifier="t2", name="fetch", arguments={"url": "y"}),
    ]
    kind, text, content_json, tool_calls, tool_response = classify_message(
        AssistantMessage(calls)
    )
    assert kind == "tool_calls"
    assert text is None
    assert [c["identifier"] for c in content_json] == ["t1", "t2"]
    assert [c.identifier for c in tool_calls] == ["t1", "t2"]
    assert tool_response is None


def test_classify_tool_response_message() -> None:
    response = ToolResponse(identifier="t1", name="search", result="found it")
    kind, text, content_json, tool_calls, tool_response = classify_message(
        ToolMessage(response)
    )
    assert kind == "tool_response"
    assert content_json["result"] == "found it"
    assert tool_response is response


def test_classify_base_model_message() -> None:
    class Out(BaseModel):
        score: int

    kind, text, content_json, _, _ = classify_message(AssistantMessage(Out(score=7)))
    assert kind == "model"
    assert content_json == {"score": 7}
