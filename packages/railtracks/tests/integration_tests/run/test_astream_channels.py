"""Integration tests for named channels on `rt.astream`: `rt.broadcast(channel=)` +
`Stream.on_channel(...)`."""

import pytest
import railtracks as rt


@rt.function_node
async def multi_channel() -> str:
    """Emits one-off events across two named channels within a streamed run."""
    await rt.broadcast("d1", channel="default")
    await rt.broadcast("s1", channel="status")
    await rt.broadcast("d2", channel="default")
    return "done"


@pytest.mark.asyncio
async def test_astream_yields_all_channels_by_default():
    with rt.Session(flow_name="chan"):
        chunks = [c async for c in rt.astream(multi_channel)]
    assert chunks == ["d1", "s1", "d2"]


@pytest.mark.asyncio
async def test_on_channel_filters_to_one_channel():
    with rt.Session(flow_name="chan"):
        stream = rt.astream(multi_channel).on_channel("status")
        chunks = [c async for c in stream]
        assert chunks == ["s1"]
        assert stream.result == "done"

        default_only = [c async for c in rt.astream(multi_channel).on_channel("default")]
        assert default_only == ["d1", "d2"]


@pytest.mark.asyncio
async def test_on_channel_unused_yields_nothing_but_result_intact():
    with rt.Session(flow_name="chan"):
        stream = rt.astream(multi_channel).on_channel("does-not-exist")
        chunks = [c async for c in stream]
        assert chunks == []
        assert stream.result == "done"


@pytest.mark.asyncio
async def test_on_channel_after_iteration_raises():
    with rt.Session(flow_name="chan"):
        stream = rt.astream(multi_channel)
        await stream.__anext__()
        with pytest.raises(RuntimeError):
            stream.on_channel("default")
        await stream  # let the run finish


@pytest.mark.asyncio
async def test_agent_tokens_ride_default_channel(mock_llm):
    agent = rt.agent_node(
        name="Streamer",
        llm=mock_llm(custom_response="hello"),
        system_message="s",
    )
    with rt.Session(flow_name="chan"):
        tokens = [
            c async for c in rt.astream(agent, user_input="hi").on_channel("default")
        ]
    assert "".join(tokens) == "hello"
