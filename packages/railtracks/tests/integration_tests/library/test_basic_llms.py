import pytest
import railtracks as rt
from typing import Generator
import json

from railtracks.built_nodes.concrete.response import LLMResponse, StringResponse, StructuredResponse
from railtracks.llm.message import Role


@pytest.mark.parametrize("user_input_factory", [
    lambda: rt.llm.MessageHistory([rt.llm.UserMessage("hello world")]),
    lambda: "hello world",
    lambda: rt.llm.UserMessage("hello world"),
], ids=["message_history", "string", "user_message"])
@pytest.mark.asyncio
async def test_ternial_llm_run_with_different_inputs(mock_llm, encoder_system_message, user_input_factory):
    """Test that the agent can be called with different input types."""
    encoder_agent = rt.agent_node(
        name="Encoder",
        system_message=encoder_system_message,
        llm=mock_llm(),
    )

    user_input = user_input_factory()
    response = await rt.call(encoder_agent, user_input=user_input)

    assert isinstance(response.text, str)


@pytest.mark.parametrize("user_input_factory", [
    lambda: rt.llm.MessageHistory([rt.llm.UserMessage("Generate a simple text and number.")]),
    lambda: rt.llm.UserMessage("Generate a simple text and number."),
    lambda: [rt.llm.Message(role=Role.user, content="Generate a simple text and number.")],
    lambda: "Generate a simple text and number.",
], ids=["message_history", "user_message", "list_of_messages", "string_message"])
@pytest.mark.asyncio
async def test_structured_llm_run_with_different_inputs(mock_llm, simple_output_model, user_input_factory):
    """Test that the structured agent can be called with different input types."""

    # mock_llm will try to populate the structured output with the provided dict
    structured_llm = mock_llm('{"text":"hello world", "number":"42"}')

    simple_agent = rt.agent_node(
        name="Simple LLM",
        system_message="You are a helpful assistant that extracts person information.",
        llm=structured_llm,
        output_schema=simple_output_model,
    )

    with rt.Session(logging_setting="NONE"):
        user_input = user_input_factory()
        response = await rt.call(simple_agent, user_input=user_input)

        assert isinstance(response.content, simple_output_model)
        assert isinstance(response.content.text, str)
        assert isinstance(response.content.number, int)

@pytest.mark.asyncio
async def test_terminal_llm_streaming(mock_llm):
    """Test that the terminal LLM can stream responses."""
    llm = mock_llm(stream=True, custom_response="hello world")

    agent = rt.agent_node(
        name="Terminal LLM",
        system_message="You are a helpful assistant.",
        llm=llm,
    )

    with rt.Session(logging_setting="NONE"):
        response = await rt.call(agent, user_input=rt.llm.MessageHistory([rt.llm.UserMessage("hello world")]))
        accumulated_text = ""
        for chunk in response:
            assert isinstance(chunk, (str, StringResponse))
            if isinstance(chunk, StringResponse):
                assert isinstance(chunk.text, str)
                assert chunk.text == "hello world"
            if isinstance(chunk, str):
                accumulated_text += chunk
            
        assert accumulated_text == "hello world"


@pytest.mark.asyncio
async def test_structured_llm_streaming(mock_llm, simple_output_model):
    """Test Structured LLM streaming."""
    llm = mock_llm(stream=True, custom_response='{"text":"hello world", "number":"42"}')

    agent = rt.agent_node(
        name="Structured LLM",
        system_message="You are a helpful assistant.",
        llm=llm,
        output_schema=simple_output_model,
    )

    with rt.Session(logging_setting="NONE"):
        response = await rt.call(agent, user_input=rt.llm.MessageHistory([rt.llm.UserMessage("hello world")]))
        accumulated_text = ""
        for chunk in response:
            assert isinstance(chunk, (str, StructuredResponse))

            if isinstance(chunk, StructuredResponse):
                assert isinstance(chunk.structured, simple_output_model)
                assert chunk.structured.text == "hello world"
                assert chunk.structured.number == 42

            if isinstance(chunk, str):
                accumulated_text += chunk

        assert accumulated_text == '{"text":"hello world","number":42}'





