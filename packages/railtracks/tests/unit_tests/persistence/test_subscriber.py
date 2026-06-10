"""PersistenceSubscriber diff-sync tests against real forests + tmp SQLite."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from railtracks.llm import AssistantMessage, MessageHistory, UserMessage
from railtracks.persistence.models import (
    LLMCallRow,
    NodeRow,
    RequestRow,
    RunRow,
    SessionRow,
    StampRow,
)
from railtracks.persistence.repository import SessionRepository
from railtracks.persistence.subscriber import PersistenceSubscriber
from railtracks.pubsub.messages import FatalFailure
from railtracks.state.info import ExecutionInfo
from railtracks.state.request import Failure


class _FakeNode:
    """Duck-typed Node: the subscriber/mappers touch uuid, name(), type(), details."""

    def __init__(self, uuid: str, name: str = "FakeAgent", node_type: str = "Agent"):
        self.uuid = uuid
        self._name = name
        self._type = node_type
        self.details = {"llm_details": []}

    def name(self) -> str:
        return self._name

    def type(self) -> str:
        return self._type


@pytest.fixture
def repo(tmp_railtracks_home: Path) -> SessionRepository:
    r = SessionRepository(tmp_railtracks_home)
    r.start_session(
        session_id="s-1",
        flow_id="f-1",
        flow_name="demo",
        session_name=None,
        start_time=0.0,
    )
    return r


@pytest.fixture
def info() -> ExecutionInfo:
    return ExecutionInfo.create_new()


@pytest.fixture
def sub(repo: SessionRepository, info: ExecutionInfo) -> PersistenceSubscriber:
    return PersistenceSubscriber(repo, session_id="s-1", info=info)


def _all(repo: SessionRepository, model):
    with Session(repo._engine) as s:
        return s.exec(select(model)).all()


def _spawn_root(info: ExecutionInfo, node: _FakeNode, request_id: str = "run-1"):
    stamp = info.stamper.create_stamp("created root")
    info.node_forest.update(node, stamp)
    info.request_forest.create(
        identifier=request_id,
        source_id=None,
        sink_id=node.uuid,
        input_args=("hello",),
        input_kwargs={},
        stamp=stamp,
    )
    return stamp


def test_open_run_node_request_persisted(sub, info, repo) -> None:
    _spawn_root(info, _FakeNode("n-root"))
    sub.sync()

    runs = _all(repo, RunRow)
    assert len(runs) == 1 and runs[0].run_id == "run-1" and runs[0].status == "Open"
    nodes = _all(repo, NodeRow)
    assert len(nodes) == 1 and nodes[0].node_uuid == "n-root"
    requests = _all(repo, RequestRow)
    assert len(requests) == 1 and requests[0].status == "Open"


def test_completion_closes_request_and_run(sub, info, repo) -> None:
    node = _FakeNode("n-root")
    _spawn_root(info, node)
    sub.sync()

    done = info.stamper.create_stamp("completed root")
    info.node_forest.update(node, done)
    info.request_forest.update("run-1", {"answer": 42}, done)
    sub.sync()

    req = _all(repo, RequestRow)[0]
    assert req.status == "Completed"
    assert req.output_json == {"answer": 42}
    run = _all(repo, RunRow)[0]
    assert run.status == "Completed"
    assert run.end_time == done.time


def test_child_node_inherits_run(sub, info, repo) -> None:
    root = _FakeNode("n-root")
    _spawn_root(info, root)

    child = _FakeNode("n-child", name="FakeTool", node_type="Tool")
    stamp = info.stamper.create_stamp("spawned child")
    info.node_forest.update(child, stamp)
    info.request_forest.create(
        identifier="req-child",
        source_id="n-root",
        sink_id="n-child",
        input_args=(),
        input_kwargs={},
        stamp=stamp,
    )
    sub.sync()

    nodes = {n.node_uuid: n for n in _all(repo, NodeRow)}
    assert nodes["n-child"].run_id == "run-1"
    assert nodes["n-child"].node_type == "Tool"
    # still a single run row
    assert len(_all(repo, RunRow)) == 1


def test_sync_is_idempotent(sub, info, repo) -> None:
    _spawn_root(info, _FakeNode("n-root"))
    sub.sync()
    sub.sync()
    sub.sync()

    assert len(_all(repo, RunRow)) == 1
    assert len(_all(repo, NodeRow)) == 1
    assert len(_all(repo, RequestRow)) == 1


def test_llm_details_persist_incrementally(sub, info, repo) -> None:
    node = _FakeNode("n-root")
    _spawn_root(info, node)

    def _details() -> SimpleNamespace:
        return SimpleNamespace(
            input=MessageHistory([UserMessage("hi")]),
            output=AssistantMessage("hello"),
            model_name="gpt-4o",
            model_provider="openai",
            input_tokens=10,
            output_tokens=5,
            total_cost=0.001,
            system_fingerprint=None,
            latency=0.2,
        )

    node.details["llm_details"].append(_details())
    sub.sync()
    assert len(_all(repo, LLMCallRow)) == 1

    node.details["llm_details"].append(_details())
    sub.sync()
    calls = _all(repo, LLMCallRow)
    assert len(calls) == 2
    assert sorted(c.call_index for c in calls) == [0, 1]

    # nothing new -> nothing duplicated
    sub.sync()
    assert len(_all(repo, LLMCallRow)) == 2


def test_failure_output_writes_failure_state(sub, info, repo) -> None:
    node = _FakeNode("n-root")
    _spawn_root(info, node)
    sub.sync()

    boom = info.stamper.create_stamp("failed root")
    info.request_forest.update("run-1", Failure(ValueError("boom")), boom)
    sub.sync()

    req = _all(repo, RequestRow)[0]
    assert req.status == "Failed"
    assert req.output_kind == "failure"
    assert _all(repo, RunRow)[0].status == "Failed"


async def test_fatal_failure_marks_session_failed(sub, repo) -> None:
    await sub.handle(FatalFailure(error=RuntimeError("meltdown")))
    row = _all(repo, SessionRow)[0]
    assert row.status == "Failed"
    assert row.end_time is not None


def test_stamps_persist_incrementally(sub, info, repo) -> None:
    _spawn_root(info, _FakeNode("n-root"))
    sub.sync()
    first_count = len(_all(repo, StampRow))
    assert first_count >= 1

    info.stamper.create_stamp("extra step")
    sub.sync()
    assert len(_all(repo, StampRow)) == first_count + 1
