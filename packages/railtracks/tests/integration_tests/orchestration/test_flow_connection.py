import asyncio
import time

import pytest
import railtracks as rt
from railtracks.orchestration.connection import FlowConnection, NodeMessageHistory


@rt.function_node
async def writes_context(text: str) -> str:
    rt.context.put("stage", "running")
    await asyncio.sleep(0)
    rt.context.put("stage", "done")
    rt.context.put("seen", text)
    return f"processed:{text}"


@rt.function_node
async def fails_midway(text: str) -> str:
    rt.context.put("stage", "about to fail")
    await asyncio.sleep(0)
    raise ValueError("node blew up")


# Module level rather than in the flow context, which is deepcopied per run.
_gate: asyncio.Event


@rt.function_node
async def waits_on_gate(text: str) -> str:
    rt.context.put("stage", "running")
    await _gate.wait()
    rt.context.put("stage", "done")
    return f"processed:{text}"


@pytest.fixture
def flow():
    return rt.Flow(
        name="conn_test",
        entry_point=writes_context,
        context={"stage": "not started"},
        save_state=False,
    )


@pytest.fixture
def failing_flow():
    return rt.Flow(
        name="conn_fail",
        entry_point=fails_midway,
        context={"stage": "not started"},
        save_state=False,
    )


def nested_flow(mock_llm):
    """A function node delegating to two agents, so histories nest."""
    researcher = rt.agent_node(
        name="Researcher",
        system_message="You research.",
        llm=mock_llm(custom_response="facts"),
    )
    writer = rt.agent_node(
        name="Writer",
        system_message="You write.",
        llm=mock_llm(custom_response="summary"),
    )

    @rt.function_node
    async def pipeline(topic: str) -> str:
        facts = await rt.call(researcher, topic)
        summary = await rt.call(writer, facts.text)
        return summary.text

    return rt.Flow(name="nested", entry_point=pipeline, save_state=False)


class TestConnect:
    def test_returns_a_connection(self, flow):
        assert isinstance(flow.connect(), FlowConnection)

    def test_each_call_is_a_new_connection(self, flow):
        assert flow.connect() is not flow.connect()

    async def test_result_matches_plain_ainvoke(self, flow):
        assert await flow.connect().ainvoke("x") == await flow.ainvoke("x")

    def test_result_matches_plain_invoke(self, flow):
        assert flow.connect().invoke("x") == flow.invoke("x")

    async def test_plain_ainvoke_return_value_is_untouched(self, flow):
        result = await flow.ainvoke("x")
        assert result == "processed:x"
        assert not hasattr(result, "run_info")


class TestContext:
    async def test_readable_after_the_run(self, flow):
        conn = flow.connect()
        await conn.ainvoke("hello")
        assert conn.context.get("stage") == "done"
        assert conn.context.get("seen") == "hello"

    async def test_is_live_while_in_flight(self):
        global _gate
        _gate = asyncio.Event()

        flow = rt.Flow(
            name="conn_gated",
            entry_point=waits_on_gate,
            context={"stage": "not started"},
            save_state=False,
        )
        conn = flow.connect()
        task = asyncio.create_task(conn.ainvoke("hello"))

        async def reached_running():
            while not (conn.connected and conn.context.get("stage") == "running"):
                await asyncio.sleep(0)

        await asyncio.wait_for(reached_running(), timeout=5)
        assert conn.context.get("stage") == "running"

        _gate.set()
        await task
        assert conn.context.get("stage") == "done"

    async def test_readable_after_a_failure(self, failing_flow):
        conn = failing_flow.connect()
        with pytest.raises(ValueError):
            await conn.ainvoke("boom")
        assert conn.context.get("stage") == "about to fail"

    async def test_reflects_the_most_recent_invocation(self, flow):
        conn = flow.connect()
        await conn.ainvoke("first")
        first_session = conn.session_id
        await conn.ainvoke("second")

        assert conn.context.get("seen") == "second"
        assert conn.session_id != first_session

    async def test_connections_are_isolated(self, flow):
        conns = [flow.connect() for _ in range(3)]
        await asyncio.gather(*(c.ainvoke(f"job-{i}") for i, c in enumerate(conns)))

        assert [c.context.get("seen") for c in conns] == ["job-0", "job-1", "job-2"]
        assert len({c.session_id for c in conns}) == 3


class TestBeforeAnythingRuns:
    def test_connected_is_false(self, flow):
        assert flow.connect().connected is False

    @pytest.mark.parametrize(
        "accessor",
        ["context", "session", "session_id"],
    )
    def test_accessors_raise(self, flow, accessor):
        with pytest.raises(RuntimeError, match="Nothing has run on this connection"):
            getattr(flow.connect(), accessor)

    def test_message_histories_raises(self, flow):
        with pytest.raises(RuntimeError, match="Nothing has run on this connection"):
            flow.connect().message_histories()

    async def test_connected_is_true_afterwards(self, flow):
        conn = flow.connect()
        await conn.ainvoke("x")
        assert conn.connected is True


class TestOneInvocationAtATime:
    async def test_concurrent_reuse_raises(self, flow):
        conn = flow.connect()
        task = asyncio.create_task(conn.ainvoke("a"))
        await asyncio.sleep(0)

        with pytest.raises(RuntimeError, match="already running an invocation"):
            await conn.ainvoke("b")

        await task

    async def test_sequential_reuse_is_allowed(self, flow):
        conn = flow.connect()
        assert await conn.ainvoke("a") == "processed:a"
        assert await conn.ainvoke("b") == "processed:b"

    async def test_released_after_a_failure(self, failing_flow):
        conn = failing_flow.connect()
        with pytest.raises(ValueError):
            await conn.ainvoke("boom")

        # the guard must not latch on the way out
        with pytest.raises(ValueError):
            await conn.ainvoke("boom")


class TestMessageHistories:
    async def test_empty_when_no_model_was_called(self, flow):
        conn = flow.connect()
        await conn.ainvoke("x")
        assert conn.message_histories() == []

    async def test_includes_nested_agents_in_order(self, mock_llm):
        conn = nested_flow(mock_llm).connect()
        await conn.ainvoke("topic")

        histories = conn.message_histories()
        assert [h.node_name for h in histories] == ["Researcher", "Writer"]
        assert all(isinstance(h, NodeMessageHistory) for h in histories)

    async def test_carries_the_conversation(self, mock_llm):
        conn = nested_flow(mock_llm).connect()
        await conn.ainvoke("topic")

        researcher = conn.message_histories()[0]
        roles = [str(m.role) for m in researcher.message_history]
        contents = [str(m.content) for m in researcher.message_history]

        assert roles == ["Role.user", "Role.assistant"]
        assert contents == ["topic", "facts"]

    async def test_identifies_the_node(self, mock_llm):
        conn = nested_flow(mock_llm).connect()
        await conn.ainvoke("topic")

        for history in conn.message_histories():
            assert history.node_id
            assert history.request_id
            assert history.node_id != history.request_id

    async def test_not_ordered_by_completion(self, mock_llm):
        """
        Agents called A, B, C whose models finish C, B, A must not come back C, B, A.

        `asyncio.gather` does not promise scheduling order, so the exact sequence
        is not contractual -- but it must not be completion order, which would
        reverse the common fan-out.
        """

        class SlowLLM(mock_llm):
            def __init__(self, delay: float, **kwargs):
                super().__init__(**kwargs)
                self.delay = delay

            def _chat(self, messages, **kwargs):
                # model.chat runs via asyncio.to_thread, so this really overlaps
                time.sleep(self.delay)
                return self._base_chat()

        agents = [
            rt.agent_node(
                name=name,
                system_message="s",
                llm=SlowLLM(delay, custom_response=name),
            )
            for name, delay in [("A", 0.30), ("B", 0.15), ("C", 0.01)]
        ]

        @rt.function_node
        async def fan_out(topic: str) -> str:
            await asyncio.gather(*(rt.call(a, topic) for a in agents))
            return "done"

        conn = rt.Flow(
            name="conn_fan_out", entry_point=fan_out, save_state=False
        ).connect()
        await conn.ainvoke("topic")

        names = [h.node_name for h in conn.message_histories()]
        assert sorted(names) == ["A", "B", "C"]
        assert names != ["C", "B", "A"]


class TestSession:
    async def test_exposes_the_backing_session(self, flow):
        conn = flow.connect()
        await conn.ainvoke("x")
        assert conn.session.payload()["session_id"] == conn.session_id

    async def test_reachable_after_the_run_closes(self, flow):
        conn = flow.connect()
        await conn.ainvoke("x")
        assert conn.session.info.answer is not None


class TestRepr:
    def test_before_invocation(self, flow):
        assert "not yet invoked" in repr(flow.connect())

    async def test_after_invocation(self, flow):
        conn = flow.connect()
        await conn.ainvoke("x")
        assert conn.session_id in repr(conn)
