import pytest
import railtracks as rt
from railtracks.llm import Message
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
        llm_model=mock_llm(Message(content="encoder check", role="assistant")),
        manifest=encoder_manifest,
    )
    decoder = rt.agent_node(
        name="Decoder",
        system_message=decoder_system_message,
        llm_model=mock_llm(Message(content="decoder check", role="assistant")),
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

    # ======== mock chat_with tools =========
    async def child_llms_invoke(messages, tools):
        assert len(tools) == 2
        _check_tool_info(tools[0])
        _check_tool_info(tools[1])

        encoder_tool_terminal = encoder.prepare_tool({"text_input": "hello world"})
        decoder_tool_terminal = decoder.prepare_tool({"bytes_input": "hello world"})

        contracts = [encoder_tool_terminal.invoke(), decoder_tool_terminal.invoke()]
        tool_responses = await asyncio.gather(*contracts)

        assert tool_responses[0].content == "encoder check"
        assert tool_responses[1].content == "decoder check"

        return Response(Message(content=str("Both children returned the correct response"), role="assistant"))


    randomizer_llm = mock_llm()
    randomizer_llm._achat_with_tools = child_llms_invoke
    # ========================================
    randomizer = rt.agent_node(
        tool_nodes={encoder, decoder},
        llm_model=randomizer_llm,
        name="Randomizer",
        system_message=system_randomizer,
    )

    with rt.Session(logging_setting="NONE"):
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("The input string is 'hello world'")]
        )
        response = await rt.call(randomizer, user_input=message_history)
        assert response.content == "Both children returned the correct response"


@pytest.mark.asyncio
async def test_terminal_llm_as_tool_correct_initialization_no_params(mock_llm):

    rng_tool_details = "A tool that generates 5 random integers between 1 and 100."

    rng_node = rt.agent_node(
        name="RNG Tool",
        system_message="You are a helful assistant that can generate 5 random numbers between 1 and 100.",
        llm_model=mock_llm(custom_response_message=Message(content="[42, 42, 42, 42, 42]", role="assistant")),    # Assert this is propogated to the parent llm
        manifest=rt.ToolManifest(rng_tool_details, None),
    )

    assert rng_node.tool_info().name == "RNG_Tool"
    assert rng_node.tool_info().detail == rng_tool_details
    assert rng_node.tool_info().parameters == []

    system_message = "You are a math genius that calls the RNG tool to generate 5 random numbers between 1 and 100 and gives the sum of those numbers."

    # ======== mock chat_with tools =========
    async def child_llm_invoke(messages, tools):
        assert len(tools) == 1
        assert tools[0].name == "RNG_Tool"
        # once asserted, we can call the child node and return the result
        rng_tool_terminal = rng_node.prepare_tool({})
        response = await rng_tool_terminal.invoke()
        return Response(Message(content=str(response.content), role="assistant"))


    math_llm = mock_llm()
    math_llm._achat_with_tools = child_llm_invoke
    # ========================================

    math_node = rt.agent_node(
        tool_nodes={rng_node},
        name="Math Node",
        system_message=system_message,
        llm_model=math_llm,
    )

    with rt.Session(logging_setting="NONE") as runner:
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Start the Math node.")]
        )
        response = await rt.call(math_node, user_input=message_history)
        
        assert response.content == '[42, 42, 42, 42, 42]'

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
        llm_model=mock_llm(custom_response_message=Message(content="Encoder ran successfully", role="assistant")),
        manifest=rt.ToolManifest(encoder_tool_details, encoder_tool_params),
    )

    # ======== mock chat_with tools =========
    async def child_llm_invoke(messages, tools):    
        assert len(tools) == 1
        assert tools[0].name == "Encoder"

        # once asserted, we can call the child node and return the result
        try:
            encoder_tool_terminal = encoder.prepare_tool({"invalid_arg_name": "hello world"})
        except Exception as e:  
            assert isinstance(e, KeyError)  # we expect the child to raise a KeyError
            encoder_tool_terminal = encoder.prepare_tool({"text_input": "hello world"})

        response = await encoder_tool_terminal.invoke()
        assert response.content == "Encoder ran successfully"

        return Response(Message(content="There was an error running the tool", role="assistant"))


    invalid_caller_llm = mock_llm()
    invalid_caller_llm._achat_with_tools = child_llm_invoke
    # ========================================


    system_message = "You are a helful assitant. Use the encoder tool with invalid parameters (invoke the tool with invalid parameters) once and then invoke it again with valid parameters."
    tool_call_llm = rt.agent_node(
        tool_nodes={encoder},
        llm_model=invalid_caller_llm,
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
            message.role == "assistant" and "There was an error running the tool" in message.content
            for message in response.message_history
        )

def test_no_manifest():
    agent = rt.agent_node(name="not a tool")
    with pytest.raises(NotImplementedError):
        agent.tool_info()

# ====================================================== END terminal_llm as tool ========================================================