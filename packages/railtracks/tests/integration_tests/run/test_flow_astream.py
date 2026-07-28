"""Integration tests for `Flow.astream`: streaming a flow's entry point in a
flow-configured session that opens on first iteration and closes on completion."""

import pytest
import railtracks as rt


@pytest.mark.asyncio
async def test_flow_astream_yields_chunks_and_result(mock_llm):
    agent = rt.agent_node(
        name="Streamer", llm=mock_llm(custom_response="hello"), system_message="s"
    )
    flow = rt.Flow(name="poem", entry_point=agent)

    stream = flow.astream("hi")
    chunks = [c async for c in stream]

    assert "".join(chunks) == "hello"
    assert stream.result.text == "hello"


@pytest.mark.asyncio
async def test_flow_astream_awaitable(mock_llm):
    agent = rt.agent_node(
        name="Streamer", llm=mock_llm(custom_response="world"), system_message="s"
    )
    flow = rt.Flow(name="poem", entry_point=agent)

    final = await flow.astream("hi")
    assert final.text == "world"


@pytest.mark.asyncio
async def test_flow_astream_closes_session(mock_llm):
    """After the stream completes the flow's session is torn down (no active context)."""
    from railtracks.context.central import is_context_present

    agent = rt.agent_node(
        name="Streamer", llm=mock_llm(custom_response="x"), system_message="s"
    )
    flow = rt.Flow(name="poem", entry_point=agent)

    async for _ in flow.astream("hi"):
        pass

    assert not is_context_present()


@pytest.mark.asyncio
async def test_flow_astream_applies_flow_stream_callback(mock_llm):
    """The stream lane callback configured on the Flow receives the streamed chunks."""
    seen: list[str] = []
    agent = rt.agent_node(
        name="Streamer", llm=mock_llm(custom_response="abc"), system_message="s"
    )
    flow = rt.Flow(name="poem", entry_point=agent, stream_callback=seen.append)

    await flow.astream("hi")
    assert "".join(seen) == "abc"


@pytest.mark.asyncio
async def test_flow_astream_on_channel(mock_llm):
    """on_channel works on a flow stream, same as rt.astream (tokens ride 'default')."""
    agent = rt.agent_node(
        name="Streamer", llm=mock_llm(custom_response="tok"), system_message="s"
    )
    flow = rt.Flow(name="poem", entry_point=agent)

    chunks = [c async for c in flow.astream("hi").on_channel("default")]
    assert "".join(chunks) == "tok"
