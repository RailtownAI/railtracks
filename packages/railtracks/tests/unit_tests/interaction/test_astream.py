"""An `rt.astream` closes its run however the reader leaves it: read to the end, broken
out of, or cancelled. Each case must leave the caller's context clear and no task running."""

import asyncio

import pytest
import railtracks as rt
from railtracks.context.central import is_context_active, is_context_present
from railtracks.observability import Event, configure_writers


class _Collecting:
    def __init__(self):
        self.events: list[Event] = []

    def start(self):
        pass

    def write(self, event: Event):
        self.events.append(event)

    def shutdown(self):
        pass


@pytest.fixture
def writer():
    w = _Collecting()
    configure_writers([w])
    return w


def _completed(events: list[Event]) -> list[Event]:
    return [e for e in events if e.event_type == "session.completed"]


async def _settle(timeout: float = 2.0) -> list[asyncio.Task]:
    """Waits for every task but the current one to finish; returns any still running."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        others = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if not others or loop.time() >= deadline:
            return others
        await asyncio.sleep(0.01)


def _agent(llm: rt.llm.ModelBase):
    return rt.agent_node(name="Streamer", system_message="stream", llm=llm)


async def test_a_fully_read_stream_closes_its_run(writer, mock_llm):
    stream = rt.astream(_agent(mock_llm(custom_response="Echo")), user_input="go")
    chunks = [chunk async for chunk in stream]

    assert chunks == ["E", "c", "h", "o"]
    assert stream.result.text == "Echo"
    assert not is_context_present()
    assert await _settle() == []
    assert [e.payload["status"] for e in _completed(writer.events)] == ["success"]


async def test_breaking_out_of_a_stream_still_closes_its_run(writer, mock_llm):
    stream = rt.astream(_agent(mock_llm(custom_response="abcdef")), user_input="go")
    async for _ in stream:
        break

    assert not is_context_present()
    assert not is_context_active()
    assert await _settle() == []
    # the run is not cancelled by the break: it finishes and records its real outcome
    assert [e.payload["status"] for e in _completed(writer.events)] == ["success"]


async def test_cancelling_the_reader_cancels_and_closes_the_run(writer, mock_llm):
    class _SlowLLM(mock_llm):
        async def _astream_chat(self, messages, **kwargs):
            yield "a"
            await asyncio.sleep(0.2)
            yield "b"

    first_chunk = asyncio.Event()
    reader_context: dict[str, bool] = {}

    async def reader():
        try:
            async for _ in rt.astream(_agent(_SlowLLM()), user_input="go"):
                first_chunk.set()
        except asyncio.CancelledError:
            reader_context["present"] = is_context_present()
            raise

    task = asyncio.create_task(reader())
    await asyncio.wait_for(first_chunk.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert reader_context == {"present": False}
    assert not is_context_present()
    assert await _settle() == []
    assert [e.payload["status"] for e in _completed(writer.events)] == ["failure"]
