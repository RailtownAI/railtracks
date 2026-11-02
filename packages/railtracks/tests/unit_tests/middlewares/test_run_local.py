"""RunLocal: middleware attributes that hold a separate value for each run."""

from __future__ import annotations

import asyncio

import pytest
import railtracks as rt
from railtracks.middleware import Middleware, RunLocal


class CountCalls(Middleware):
    calls = RunLocal(int)

    def __init__(self):
        super().__init__(self._middleware_fn)

    async def _middleware_fn(self, call, *args, **kwargs):
        self.calls += 1
        return await call(*args, **kwargs)


class RecordArgs(Middleware):
    seen = RunLocal(list)
    calls = RunLocal(int)

    def __init__(self, label: str):
        self.label = label
        super().__init__(self._middleware_fn)

    async def _middleware_fn(self, call, *args, **kwargs):
        self.seen.append(kwargs.get("x"))
        self.calls += 1
        return await call(*args, **kwargs)


def _counting_driver(mw: Middleware, *, report):
    @rt.function_node(middleware=[mw])
    async def tool(x: str) -> str:
        await asyncio.sleep(0)
        return x

    @rt.function_node
    async def driver(n: int):
        for i in range(n):
            await rt.call(tool, x=str(i))
        return report()

    return driver


# ================================ per run ================================


def test_each_run_starts_from_the_default():
    counter = CountCalls()
    flow = rt.Flow(
        "fresh-runs",
        entry_point=_counting_driver(counter, report=lambda: counter.calls),
    )

    assert flow.invoke(n=3) == 3
    assert flow.invoke(n=2) == 2


def test_concurrent_runs_keep_separate_values():
    counter = CountCalls()
    driver = _counting_driver(counter, report=lambda: counter.calls)

    async def run_both():
        return await asyncio.gather(
            rt.Flow("concurrent-a", entry_point=driver).ainvoke(n=3),
            rt.Flow("concurrent-b", entry_point=driver).ainvoke(n=5),
        )

    assert asyncio.run(run_both()) == [3, 5]


def test_one_instance_on_two_nodes_shares_its_value_within_a_run():
    counter = CountCalls()

    @rt.function_node(middleware=[counter])
    def tool_a(x: str) -> str:
        return x

    @rt.function_node(middleware=[counter])
    def tool_b(x: str) -> str:
        return x

    @rt.function_node
    async def driver() -> int:
        await rt.call(tool_a, x="a")
        await rt.call(tool_b, x="b")
        await rt.call(tool_a, x="c")
        return counter.calls

    assert rt.Flow("shared-in-run", entry_point=driver).invoke() == 3


def test_mutable_default_is_fresh_in_every_run():
    recorder = RecordArgs("r")
    flow = rt.Flow(
        "fresh-list",
        entry_point=_counting_driver(recorder, report=lambda: list(recorder.seen)),
    )

    assert flow.invoke(n=2) == ["0", "1"]
    assert flow.invoke(n=1) == ["0"]


def test_two_instances_of_one_class_keep_separate_values():
    first, second = CountCalls(), CountCalls()

    @rt.function_node(middleware=[first])
    def tool_a(x: str) -> str:
        return x

    @rt.function_node(middleware=[second])
    def tool_b(x: str) -> str:
        return x

    @rt.function_node
    async def driver() -> tuple[int, int]:
        await rt.call(tool_a, x="a")
        await rt.call(tool_a, x="b")
        await rt.call(tool_b, x="c")
        return first.calls, second.calls

    assert rt.Flow("two-instances", entry_point=driver).invoke() == (2, 1)


def test_fields_on_one_instance_are_independent():
    recorder = RecordArgs("r")
    flow = rt.Flow(
        "two-fields",
        entry_point=_counting_driver(
            recorder, report=lambda: (recorder.calls, list(recorder.seen))
        ),
    )

    assert flow.invoke(n=2) == (2, ["0", "1"])


def test_plain_attributes_stay_shared():
    recorder = RecordArgs("configured")
    flow = rt.Flow(
        "plain-attr",
        entry_point=_counting_driver(recorder, report=lambda: recorder.label),
    )

    assert flow.invoke(n=1) == "configured"
    assert recorder.label == "configured"


def test_default_factory_runs_once_per_run():
    made = []

    class Tracked(Middleware):
        items = RunLocal(lambda: made.append(1) or [])

        def __init__(self):
            super().__init__(self._middleware_fn)

        async def _middleware_fn(self, call, *args, **kwargs):
            self.items.append(1)
            self.items.append(2)
            return await call(*args, **kwargs)

    tracked = Tracked()
    flow = rt.Flow(
        "factory-once",
        entry_point=_counting_driver(tracked, report=lambda: len(tracked.items)),
    )

    assert flow.invoke(n=2) == 4
    assert flow.invoke(n=1) == 2
    assert len(made) == 2


def test_subclasses_inherit_run_local_fields():
    class CountTwice(CountCalls):
        async def _middleware_fn(self, call, *args, **kwargs):
            self.calls += 2
            return await call(*args, **kwargs)

    counter = CountTwice()
    flow = rt.Flow(
        "inherited", entry_point=_counting_driver(counter, report=lambda: counter.calls)
    )

    assert flow.invoke(n=3) == 6
    assert flow.invoke(n=1) == 2


def test_model_middleware_slot_is_per_run_across_agent_invocations(mock_llm):
    class CountModelCalls(Middleware):
        calls = RunLocal(int)

        def __init__(self):
            super().__init__(self._middleware_fn)

        async def _middleware_fn(self, call, *args, **kwargs):
            self.calls += 1
            return await call(*args, **kwargs)

    counter = CountModelCalls()
    agent = rt.agent_node(
        "Agent", llm=mock_llm(custom_response="hi"), model_middleware=[counter]
    )

    @rt.function_node
    async def driver(n: int) -> int:
        for _ in range(n):
            await rt.call(agent, user_input="q")
        return counter.calls

    flow = rt.Flow("model-slot", entry_point=driver)
    assert flow.invoke(n=2) == 2
    assert flow.invoke(n=1) == 1


# ============================== outside a run ==============================


def test_outside_a_run_the_most_recent_run_stays_readable():
    counter = CountCalls()
    flow = rt.Flow(
        "readable", entry_point=_counting_driver(counter, report=lambda: None)
    )

    flow.invoke(n=3)
    assert counter.calls == 3

    flow.invoke(n=1)
    assert counter.calls == 1


def test_del_resets_the_value_it_reads():
    counter = CountCalls()
    flow = rt.Flow("reset", entry_point=_counting_driver(counter, report=lambda: None))

    flow.invoke(n=3)
    del counter.calls

    assert counter.calls == 0


def test_never_run_instance_reads_the_default():
    assert CountCalls().calls == 0
    assert RecordArgs("r").seen == []


@pytest.mark.asyncio
async def test_calls_outside_a_run_keep_a_value_of_their_own():
    async def noop():
        return None

    counter = CountCalls()
    flow = rt.Flow(
        "then-outside", entry_point=_counting_driver(counter, report=lambda: None)
    )
    await flow.ainvoke(n=3)

    # a direct call outside any run does not spend the finished run's value
    await counter.wrap(noop)()
    assert counter.calls == 1

    await counter.wrap(noop)()
    assert counter.calls == 2


def test_finished_runs_leave_nothing_on_the_instance():
    counter = CountCalls()
    flow = rt.Flow(
        "no-growth", entry_point=_counting_driver(counter, report=lambda: None)
    )

    flow.invoke(n=1)
    attributes = set(vars(counter))
    for _ in range(50):
        flow.invoke(n=1)

    assert set(vars(counter)) == attributes
    assert counter._last_run_state == {"calls": 1}


# ================================ declaring ================================


def test_class_access_returns_the_descriptor():
    assert isinstance(CountCalls.calls, RunLocal)


def test_declaring_on_a_class_that_is_not_middleware_raises():
    with pytest.raises(Exception) as excinfo:

        class NotMiddleware:
            calls = RunLocal(int)

    # Python < 3.12 wraps errors raised by __set_name__ in a RuntimeError
    error = excinfo.value.__cause__ or excinfo.value
    assert isinstance(error, TypeError)
    assert "must be declared on a Middleware subclass" in str(error)
