import hashlib
import json

import pytest
import railtracks as rt
import railtracks.context.central as central
from railtracks.llm import ToolCall
from railtracks.llm.message import AssistantMessage
from railtracks.llm.response import Response
from railtracks.observability import JsonlWriter, configure, configure_writers

MODEL_CALLS = 20


@pytest.fixture(autouse=True)
def _clean_observability():
    central.delete_globals()
    configure.reset_for_tests()
    yield
    central.delete_globals()
    configure.reset_for_tests()


def ping() -> str:
    """Check the tool loop is alive.

    Returns:
        Always "pong".
    """
    return "pong"


async def test_pdf_is_saved_once_across_a_long_tool_loop(tmp_path, mock_llm):
    class LoopingLLM(mock_llm):
        calls = 0

        def _base_chat_with_tools(self, messages):
            LoopingLLM.calls += 1
            if LoopingLLM.calls < MODEL_CALLS:
                call = ToolCall(
                    identifier=f"c{LoopingLLM.calls}", name="ping", arguments={}
                )
                message = AssistantMessage([call])
            else:
                message = AssistantMessage("done")
            return Response(message=message, message_info=self.mocked_message_info)

    pdf_bytes = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024)
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(pdf_bytes)
    events_dir = tmp_path / "events"
    media_dir = events_dir / "media"
    configure_writers([JsonlWriter(events_dir)])

    agent = rt.agent_node(
        "Reader", llm=LoopingLLM(), tool_nodes=[rt.function_node(ping)]
    )
    history = rt.llm.MessageHistory(
        [rt.llm.UserMessage("summarize", attachment=str(pdf_path))]
    )
    await rt.Flow(name="Media Record", entry_point=agent).ainvoke(history)
    await configure.shutdown()

    assert LoopingLLM.calls == MODEL_CALLS
    assert [p.name for p in media_dir.iterdir()] == [pdf_sha256]
    assert (media_dir / pdf_sha256).read_bytes() == pdf_bytes

    [events_file] = events_dir.glob("*.jsonl")
    lines = events_file.read_text().splitlines()
    assert max(len(line.encode()) for line in lines) < 10 * 1024
    parts = [
        part
        for line in lines
        for message in json.loads(line)["payload"].get("message_input") or []
        if isinstance(message.get("content"), list)
        for part in message["content"][1:]
    ]
    assert len(parts) >= 2 * MODEL_CALLS
    assert all(p["sha256"] == pdf_sha256 for p in parts)
