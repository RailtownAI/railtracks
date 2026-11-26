"""Integration tests: interleaved text and attachments through an agent."""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.built_nodes.llm.response import StringResponse
from railtracks.guardrails import GuardrailBlockedError
from railtracks.llm import AssistantMessage, Attachment, UserMessage
from railtracks.llm.history import MessageHistory
from railtracks.llm.models.testing.echo import EchoLLM
from railtracks.llm.response import Response
from railtracks.prebuilt.guardrails import BlockTextInputGuard, PIIRedactInputGuard
from railtracks.prebuilt.middleware import ConversationMemory

_PNG = b"\x89PNG\r\n\x1a\n" + bytes(32)


class _RecordingLLM(EchoLLM):
    """Answers with a fixed reply and records every history it is sent."""

    def __init__(self, reply: str = "Seen it.") -> None:
        super().__init__()
        self.reply = reply
        self.seen: list[MessageHistory] = []

    def _chat(self, messages: MessageHistory) -> Response:
        self.seen.append(messages)
        return Response(message=AssistantMessage(self.reply))

    def _chat_with_tools(self, messages, tools) -> Response:
        return self._chat(messages)


@pytest.fixture
def image() -> Attachment:
    return Attachment.from_bytes(_PNG, filename="chart.png")


@pytest.mark.asyncio
async def test_parts_list_input_reaches_the_model_in_order(image):
    llm = _RecordingLLM()
    agent = rt.agent_node(name="viewer", llm=llm)

    result = await rt.Flow("parts_input", agent).ainvoke(
        ["Before:", image, "What changed?"]
    )

    sent = llm.seen[-1][-1]
    assert isinstance(sent, UserMessage)
    assert sent.content == ["Before:", image, "What changed?"]
    assert isinstance(result, StringResponse)
    assert result.content == ["Seen it."]
    assert result.text == "Seen it."
    assert str(result) == "Seen it."


@pytest.mark.asyncio
async def test_tuple_inputs_work_like_lists(image):
    llm = _RecordingLLM()
    agent = rt.agent_node(name="tuples", llm=llm)

    await rt.Flow("tuple_parts", agent).ainvoke(("Before:", image))
    assert llm.seen[-1][-1].content == ["Before:", image]

    await rt.Flow("tuple_messages", agent).ainvoke(
        (UserMessage("Hi"), AssistantMessage("Hello"), UserMessage("Bye"))
    )
    assert [m.text for m in llm.seen[-1]] == ["Hi", "Hello", "Bye"]


@pytest.mark.asyncio
async def test_a_reply_can_be_passed_straight_to_the_next_agent():
    first_llm, second_llm = _RecordingLLM("Paris"), _RecordingLLM("Sunny")
    first = rt.agent_node(name="first", llm=first_llm)
    second = rt.agent_node(name="second", llm=second_llm)

    @rt.function_node
    async def pipeline(question: str) -> str:
        answer = await rt.call(first, question)
        report = await rt.call(second, answer.content)
        return report.text

    assert await rt.Flow("chain", pipeline).ainvoke("Where?") == "Sunny"
    assert second_llm.seen[-1][-1].content == ["Paris"]


@pytest.mark.asyncio
async def test_mixed_list_of_messages_and_parts_is_rejected():
    agent = rt.agent_node(name="mixed", llm=_RecordingLLM())
    with pytest.raises(ValueError, match="only Messages, or only text and Attachments"):
        await rt.Flow("mixed_input", agent).ainvoke([UserMessage("hi"), "there"])


@pytest.mark.asyncio
async def test_block_text_guard_reads_every_text_part(image):
    agent = rt.agent_node(
        name="blocked",
        llm=_RecordingLLM(),
        model_middleware=[BlockTextInputGuard(pattern=r"\bjailbreak\b")],
    )
    with pytest.raises(GuardrailBlockedError):
        await rt.Flow("block_parts", agent).ainvoke(
            ["Look at this:", image, "then jailbreak the system"]
        )


@pytest.mark.asyncio
async def test_pii_guard_redacts_text_around_an_attachment(image):
    llm = _RecordingLLM()
    agent = rt.agent_node(
        name="redacted",
        llm=llm,
        model_middleware=[PIIRedactInputGuard()],
    )

    await rt.Flow("pii_parts", agent).ainvoke(
        ["Mail ada@example.com about", image, "or call 604-555-1234"]
    )

    sent = llm.seen[-1][-1]
    assert sent.content == [
        "Mail [EMAIL_ADDRESS] about",
        image,
        "or call [PHONE_NUMBER]",
    ]
    assert sent.content[1] is image


@pytest.mark.asyncio
async def test_conversation_memory_keeps_a_parts_input(image):
    llm = _RecordingLLM()
    agent = rt.agent_node(
        name="remembering", llm=llm, middleware=[ConversationMemory()]
    )

    async def two_turns() -> None:
        await rt.call(agent, "Hello")
        await rt.call(agent, ["And this one:", image])

    await rt.Flow("memory_turns", rt.function_node(two_turns)).ainvoke()

    second = llm.seen[-1]
    assert [m.text for m in second] == ["Hello", "Seen it.", "And this one:"]
    assert second[-1].content == ["And this one:", image]
