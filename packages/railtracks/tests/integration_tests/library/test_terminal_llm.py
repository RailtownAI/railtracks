import pytest
import railtracks as rt

from railtracks.llm import MessageHistory, Message
from railtracks.llm.response import Response


# ================================================ START terminal_llm basic functionality =========================================================
@pytest.mark.asyncio
async def test_terminal_llm_run(model , encoder_system_message):
    encoder_agent = rt.agent_node(
        name="Encoder",
        system_message=encoder_system_message,
        llm_model=model,
    )

    response = await rt.call(encoder_agent, user_input=rt.llm.MessageHistory([rt.llm.UserMessage("hello world")]))

    assert isinstance(response.text, str)

@pytest.mark.asyncio
async def test_terminal_llm_with_string(model, encoder_system_message):
    """Test that the easy usage wrapper can be called with a string input."""
    encoder_agent = rt.agent_node(
        name="Encoder",
        system_message=encoder_system_message,
        llm_model=model,
    )

    # Call with a string instead of MessageHistory
    response = await rt.call(encoder_agent, user_input="hello world")

    assert isinstance(response.text, str)

@pytest.mark.asyncio
async def test_terminal_llm_with_user_message(model, encoder_system_message):
    """Test that the easy usage wrapper can be called with a UserMessage input."""
    encoder_agent = rt.agent_node(
        name="Encoder",
        system_message=encoder_system_message,
        llm_model=model,
    )

    # Call with a UserMessage instead of MessageHistory
    user_msg = rt.llm.UserMessage("hello world")
    response = await rt.call(encoder_agent, user_input=user_msg)

    assert isinstance(response.text, str)

# ================================================ END terminal_llm basic functionality ===========================================================

# ================================================ START terminal_llm as tools =========================================================== 
@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_terminal_llm_as_tool_correct_initialization(
    model, encoder_system_message, decoder_system_message
):
    # We can use them as tools by creating a TerminalLLM node and passing it to the tool_call_llm node
    system_randomizer = "You are a machine that takes in string from the user and uses the encoder tool that you have on that string. Then you use the decoder tool on the output of the encoder tool. You then return the decoded string to the user."

    # Using Terminal LLMs as tools by easy_usage wrappers
    encoder_tool_details = "A tool used to encode text into bytes."
    decoder_tool_details = "A tool used to decode bytes into text."
    encoder_tool_params = {
        rt.llm.Parameter("text_input", "string", "The string to encode.")
    }
    decoder_tool_params = {
        rt.llm.Parameter("bytes_input", "string", "The bytes you would like to decode")
    }

    encoder_manifest = rt.ToolManifest(encoder_tool_details, encoder_tool_params)
    decoder_manifest = rt.ToolManifest(decoder_tool_details, decoder_tool_params)

    encoder = rt.agent_node(
        name="Encoder",
        system_message=encoder_system_message,
        llm_model=model,
        manifest=encoder_manifest,
    )
    decoder = rt.agent_node(
        name="Decoder",
        system_message=decoder_system_message,
        llm_model=model,
        manifest=decoder_manifest,
    )

    # Checking if the terminal_llms are correctly initialized
    assert (
        encoder.tool_info().name == "Encoder" and decoder.tool_info().name == "Decoder"
    )
    assert (
        encoder.tool_info().detail == encoder_tool_details
        and decoder.tool_info().detail == decoder_tool_details
    )
    encoder_params = encoder.tool_info().parameters
    decoder_params = decoder.tool_info().parameters
    
    assert all(isinstance(param, rt.llm.Parameter) for param in encoder_params), (
        f"Encoder parameters {encoder_params} should be instances of rc.llm.Parameter"
    )
    
    assert all(isinstance(param, rt.llm.Parameter) for param in decoder_params), (
        f"Decoder parameters {decoder_params} should be instances of rc.llm.Parameter"
    )

    randomizer = rt.agent_node(
        tool_nodes={encoder, decoder},
        llm_model=model,
        name="Randomizer",
        system_message=system_randomizer,
    )

    with rt.Session(logging_setting="NONE"):
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("The input string is 'hello world'")]
        )
        response = await rt.call(randomizer, user_input=message_history)
        assert any(
            message.role == "tool"
            and "There was an error running the tool" not in message.content
            for message in response.message_history
        )  # inside tool_call_llm's invoke function is this exact string in case of error


@pytest.mark.asyncio
async def test_terminal_llm_as_tool_correct_initialization_no_params(model):

    rng_tool_details = "A tool that generates 5 random integers between 1 and 100."

    rng_node = rt.agent_node(
        name="RNG Tool",
        system_message="You are a helful assistant that can generate 5 random numbers between 1 and 100.",
        llm_model=model,
        manifest=rt.ToolManifest(rng_tool_details, None),
    )

    assert rng_node.tool_info().name == "RNG_Tool"
    assert rng_node.tool_info().detail == rng_tool_details
    assert rng_node.tool_info().parameters == []

    system_message = "You are a math genius that calls the RNG tool to generate 5 random numbers between 1 and 100 and gives the sum of those numbers."

    math_node = rt.agent_node(
        tool_nodes={rng_node},
        name="Math Node",
        system_message=system_message,
        llm_model=rt.llm.OpenAILLM("gpt-4o"),
    )

    with rt.Session(logging_setting="NONE") as runner:
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Start the Math node.")]
        )
        response = await rt.call(math_node, user_input=message_history)
        assert any(
            message.role == "tool"
            and "There was an error running the tool" not in message.content
            for message in response.message_history
        )

@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_terminal_llm_tool_with_invalid_parameters(model, encoder_system_message):
    # Test case where tool is invoked with incorrect parameters
    encoder_tool_details = "A tool used to encode text into bytes."
    encoder_tool_params = {
        rt.llm.Parameter("text_input", "string", "The string to encode.")
    }

    encoder = rt.agent_node(
        name="Encoder",
        system_message=encoder_system_message,
        llm_model=model,
        manifest=rt.ToolManifest(encoder_tool_details, encoder_tool_params),
    )

    system_message = "You are a helful assitant. Use the encoder tool with invalid parameters (invoke the tool with invalid parameters) once and then invoke it again with valid parameters."
    tool_call_llm = rt.agent_node(
        tool_nodes={encoder},
        llm_model=model,
        name="InvalidToolCaller",
        system_message=system_message,
    )

    with rt.Session(
        logging_setting="VERBOSE"
    ):
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Encode this text but use an invalid parameter name.")]
        )
        response = await rt.call(tool_call_llm, user_input=message_history)
        # Check that there was an error running the tool
        assert any(
            message.role == "tool" and "There was an error running the tool" in message.content.result
            for message in response.message_history
        )


# ====================================================== END terminal_llm as tool ========================================================
