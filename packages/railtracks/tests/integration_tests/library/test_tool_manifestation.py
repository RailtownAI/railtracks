import pytest
import railtracks as rt
from railtracks.llm import Message, ToolCall
from railtracks.llm.response import Response
import asyncio

# ================================================ START terminal_llm as tools =========================================================== 
@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_terminal_llm_as_tool_correct_initialization(
    mock_llm, encoder_system_message, decoder_system_message
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
        llm=mock_llm("encoder check"),
        manifest=encoder_manifest,
    )
    decoder = rt.agent_node(
        name="Decoder",
        system_message=decoder_system_message,
        llm=mock_llm("decoder check"),
        manifest=decoder_manifest,
    )

    # Checking if the terminal_llms are correctly initialized
    def _check_tool_info(tool):
        if tool.name == "Encoder":
            assert tool.detail == encoder_tool_details
            params = tool.parameters
        elif tool.name == "Decoder":
            assert tool.detail == decoder_tool_details
            params = tool.parameters
        else:
            raise AssertionError(f"Unexpected tool: {tool.name}")

        assert all(
            isinstance(param, rt.llm.Parameter) for param in params
        ), f"Parameters of {tool.name} should be instances of rt.llm.Parameter"

    
    _check_tool_info(encoder.tool_info())
    _check_tool_info(decoder.tool_info())

    randomizer_llm = mock_llm(
        requested_tool_calls=[
            ToolCall(name="Encoder", identifier="id_42424242", arguments={"text_input": "hello world"}),
            ToolCall(name="Decoder", identifier="id_42424242", arguments={"bytes_input": "hello world"}),
        ]
    )
    # ========================================
    randomizer = rt.agent_node(
        tool_nodes={encoder, decoder},
        llm=randomizer_llm,
        name="Randomizer",
        system_message=system_randomizer,
    )

    with rt.Session(logging_setting="NONE"):
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("The input string is 'hello world'")]
        )
        response = await rt.call(randomizer, user_input=message_history)
        assert "encoder check" in response.content
        assert "decoder check" in response.content


@pytest.mark.asyncio
async def test_terminal_llm_as_tool_correct_initialization_no_params(mock_llm):

    rng_tool_details = "A tool that generates 5 random integers between 1 and 100."

    rng_node = rt.agent_node(
        name="RNG Tool",
        system_message="You are a helful assistant that can generate 5 random numbers between 1 and 100.",
        llm=mock_llm("[42, 42, 42, 42, 42]"),    # Assert this is propogated to the parent llm
        manifest=rt.ToolManifest(rng_tool_details, None),
    )

    assert rng_node.tool_info().name == "RNG_Tool"
    assert rng_node.tool_info().detail == rng_tool_details
    assert rng_node.tool_info().parameters == []

    system_message = "You are a math genius that calls the RNG tool to generate 5 random numbers between 1 and 100 and gives the sum of those numbers."

    math_llm = mock_llm(requested_tool_calls=[ToolCall(name="RNG_Tool", identifier="id_42424242", arguments={})])
    # ========================================

    math_node = rt.agent_node(
        tool_nodes={rng_node},
        name="Math Node",
        system_message=system_message,
        llm=math_llm,
    )

    with rt.Session(logging_setting="NONE") as runner:
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Start the Math node.")]
        )
        response = await rt.call(math_node, user_input=message_history)
        
        assert '[42, 42, 42, 42, 42]' in response.content

@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_terminal_llm_tool_with_invalid_parameters(mock_llm, encoder_system_message):
    # Test case where tool is invoked with incorrect parameters
    encoder_tool_details = "A tool used to encode text into bytes."
    encoder_tool_params = {
        rt.llm.Parameter("text_input", "string", "The string to encode.")
    }

    encoder = rt.agent_node(
        name="Encoder",
        system_message=encoder_system_message,
        llm=mock_llm(custom_response="Encoder ran successfully"),
        manifest=rt.ToolManifest(encoder_tool_details, encoder_tool_params),
    )

    invalid_caller_llm = mock_llm(requested_tool_calls=[ToolCall(name="encoder", identifier="id_42424242", arguments={"invalid_arg_name": "hello world"})])
    # ========================================


    system_message = "You are a helful assitant. Use the encoder tool with invalid parameters (invoke the tool with invalid parameters) once and then invoke it again with valid parameters."
    tool_call_llm = rt.agent_node(
        tool_nodes={encoder},
        llm=invalid_caller_llm,
        name="InvalidToolCaller",
        system_message=system_message,
    )

    with rt.Session(
        logging_setting="DEBUG"
    ):
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Encode this text but use an invalid parameter name.")]
        )
        response = await rt.call(tool_call_llm, user_input=message_history)
        # Check that there was an error running the tool
        assert any(
            message.role == "assistant" and "There was an error running the tool" in message.content
            for message in response.message_history
        )

def test_no_manifest():
    agent = rt.agent_node(name="not a tool")
    with pytest.raises(NotImplementedError):
        agent.tool_info()

# ====================================================== END terminal_llm as tool ========================================================