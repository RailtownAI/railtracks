"""Exercise summarization through real agent loops with deterministic models."""

import asyncio
import threading

import pytest
import railtracks as rt
from railtracks.built_nodes.llm import model_invoker
from railtracks.context.central import get_parent_id
from railtracks.events.llm import LLMResponseEvent
from railtracks.llm import AssistantMessage, Response, ToolCall, ToolMessage
from railtracks.prebuilt.middleware import ToolOutputSummarizer


@pytest.mark.parametrize("outcome", ["summary", "error", "empty", "nontext"])
async def test_each_tool_result_is_summarized_once_per_agent_run(mock_llm, outcome):
    @rt.function_node
    def large_result() -> str:
        """Return a large search result."""
        return "x" * 5_000

    seen = []
    summary_calls = []
    agent_model = mock_llm()
    summarizer = mock_llm(custom_response="SUMMARY")

    def agent_chat(messages, tools, **kwargs):
        results = [m for m in messages if isinstance(m, ToolMessage)]
        seen.append([m.content.result for m in results])
        content = (
            [
                ToolCall(
                    identifier=f"call-{len(results)}", name="large_result", arguments={}
                )
            ]
            if len(results) < 3
            else "done"
        )
        return Response(AssistantMessage(content))

    def summary_chat(messages, **kwargs):
        summary_calls.append(messages)
        if outcome == "error":
            raise RuntimeError("offline")
        content = {"summary": "SUMMARY", "empty": "  ", "nontext": None}[outcome]
        return Response(AssistantMessage(content))

    agent_model._chat_with_tools = agent_chat

    async def agent_achat(messages, tools, **kwargs):
        return agent_chat(messages, tools, **kwargs)

    agent_model._achat_with_tools = agent_achat
    summarizer._chat = summary_chat

    async def summary_achat(messages, **kwargs):
        return summary_chat(messages, **kwargs)

    summarizer._achat = summary_achat
    agent = rt.agent_node(
        name="summarized-loop",
        llm=agent_model,
        tool_nodes=[large_result],
        model_middleware=[
            ToolOutputSummarizer(
                lambda: summarizer, max_chars=1_000, summary_max_chars=100
            )
        ],
    )
    flow = rt.Flow("summarized-loop", agent)

    result = await flow.ainvoke("search three times")

    assert len(seen) == 4
    assert [len(turn) for turn in seen] == [0, 1, 2, 3]
    assert len(summary_calls) == 3
    if outcome == "summary":
        assert all(
            value == "[Summarized: original was 5,000 characters]\nSUMMARY"
            for turn in seen
            for value in turn
        )
    else:
        assert all(value == "x" * 5_000 for turn in seen for value in turn)
    assert [
        m.content.result for m in result.message_history if isinstance(m, ToolMessage)
    ] == ["x" * 5_000] * 3

    await flow.ainvoke("search three times again")
    assert len(summary_calls) == 6

    await asyncio.gather(flow.ainvoke("one run"), flow.ainvoke("another run"))
    assert len(summary_calls) == 12


async def test_parallel_results_use_observable_summary_nodes(mock_llm, monkeypatch):
    @rt.function_node
    def large_result() -> str:
        """Return a large search result."""
        return "x" * 5_000

    started = 0
    both_started = threading.Barrier(2, timeout=5)
    events = []
    summarizer = mock_llm()
    real_emit = model_invoker.emit

    async def capture(event):
        if isinstance(event, LLMResponseEvent):
            events.append((get_parent_id(), event))
        await real_emit(event)

    monkeypatch.setattr(model_invoker, "emit", capture)

    def summarize(messages, **kwargs):
        nonlocal started
        started += 1
        both_started.wait()
        return Response(
            AssistantMessage("SUMMARY"), message_info=summarizer.mocked_message_info
        )

    summarizer._chat = summarize
    agent = rt.agent_node(
        "parallel-summaries",
        llm=mock_llm(
            requested_tool_calls=[
                ToolCall(identifier=f"parallel-{i}", name="large_result", arguments={})
                for i in range(2)
            ]
        ),
        tool_nodes=[large_result],
        model_middleware=[ToolOutputSummarizer(lambda: summarizer)],
    )

    result = await rt.Flow("parallel-summaries", agent).ainvoke("search twice")

    assert started == 2
    assert result.text.count("SUMMARY") == 2
    summary_events = [
        (node, event) for node, event in events if event.output.content == "SUMMARY"
    ]
    assert len(summary_events) == 2
    assert len({node for node, _ in summary_events}) == 2
    for _, event in summary_events:
        assert event.input_tokens == 42
        assert event.output_tokens == 42
        assert event.total_cost == 0.00042
        assert event.reported_model_name == "MockLLM"
