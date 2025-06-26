import pytest
import requestcompletion as rc
from pydantic import BaseModel

# ================================================ START terminal_llm basic functionality =========================================================
@pytest.mark.asyncio
async def test_terminal_llm_easy_usage_run(model , encoder_system_message):
    encoder_agent = rc.library.terminal_llm(
        pretty_name="Encoder",
        system_message=encoder_system_message,
        model=model,
    )

    response = await rc.call(encoder_agent, message_history=rc.llm.MessageHistory([rc.llm.UserMessage("hello world")]))

    assert isinstance(response, str)

def test_terminal_llm_class_based_run(model , encoder_system_message):
    class Encoder(rc.library.TerminalLLM): 
        def __init__(
                self,
                message_history: rc.llm.MessageHistory,
                model: rc.llm.ModelBase = model,
            ):
                message_history = [x for x in message_history if x.role != "system"]
                message_history.insert(0, encoder_system_message)
                super().__init__(
                    message_history=message_history,
                    model=model,
                )
        @classmethod
        def pretty_name(cls) -> str:
            return "Simple Node"
        
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as runner:
        message_history = rc.llm.MessageHistory(
            [rc.llm.UserMessage("The input string is 'hello world'")]
        )
        response = runner.run_sync(Encoder, message_history=message_history)
        assert isinstance(response.answer, str)


# ================================================ END terminal_llm basic functionality ===========================================================

# ================================================ START terminal_llm as tools =========================================================== 
@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_terminal_llm_as_tool_correct_initialization(
    model, encoder_system_message, decoder_system_message
):
    # We can use them as tools by creating a TerminalLLM node and passing it to the tool_call_llm node
    system_randomizer = rc.llm.SystemMessage(
        "You are a machine that takes in string from the user and uses the encoder tool that you have on that string. Then you use the decoder tool on the output of the encoder tool. You then return the decoded string to the user."
    )

    # Using Terminal LLMs as tools by easy_usage wrappers
    encoder_tool_details = "A tool used to encode text into bytes."
    decoder_tool_details = "A tool used to decode bytes into text."
    encoder_tool_params = {
        rc.llm.Parameter("text_input", "string", "The string to encode.")
    }
    decoder_tool_params = {
        rc.llm.Parameter("bytes_input", "string", "The bytes you would like to decode")
    }
    encoder = rc.library.terminal_llm(
        pretty_name="Encoder",
        system_message=encoder_system_message,
        model=model,
        # tool_details and tool_parameters are required if you want to use the terminal_llm as a tool
        tool_details=encoder_tool_details,
        tool_params=encoder_tool_params,
    )
    decoder = rc.library.terminal_llm(
        pretty_name="Decoder",
        system_message=decoder_system_message,
        model=model,
        # tool_details and tool_parameters are required if you want to use the terminal_llm as a tool
        tool_details=decoder_tool_details,
        tool_params=decoder_tool_params,
    )

    # Checking if the terminal_llms are correctly initialized
    assert (
        encoder.tool_info().name == "Encoder" and decoder.tool_info().name == "Decoder"
    )
    assert (
        encoder.tool_info().detail == encoder_tool_details
        and decoder.tool_info().detail == decoder_tool_details
    )
    assert issubclass(encoder.tool_info().parameters, BaseModel) and issubclass(
        decoder.tool_info().parameters, BaseModel
    )

    randomizer = rc.library.tool_call_llm(
        connected_nodes={encoder, decoder},
        model=model,
        pretty_name="Randomizer",
        output_type="MessageHistory",
        system_message=system_randomizer,
    )

    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as runner:
        message_history = rc.llm.MessageHistory(
            [rc.llm.UserMessage("The input string is 'hello world'")]
        )
        response = await runner.run(randomizer, message_history=message_history)
        assert any(
            message.role == "tool"
            and "There was an error running the tool" not in message.content
            for message in response.answer
        )  # inside tool_call_llm's invoke function is this exact string in case of error


@pytest.mark.asyncio
async def test_terminal_llm_as_tool_correct_initialization_no_params(model):

    rng_tool_details = "A tool that generates 5 random integers between 1 and 100."

    rng_node = rc.library.terminal_llm(
        pretty_name="RNG Tool",
        system_message=rc.llm.SystemMessage(
            "You are a helful assistant that can generate 5 random numbers between 1 and 100."
        ),
        model=model,
        tool_details=rng_tool_details,
        tool_params=None,
    )

    assert rng_node.tool_info().name == "RNG_Tool"
    assert rng_node.tool_info().detail == rng_tool_details
    assert rng_node.tool_info().parameters is None

    system_message = rc.llm.SystemMessage(
        "You are a math genius that calls the RNG tool to generate 5 random numbers between 1 and 100 and gives the sum of those numbers."
    )
    math_node = rc.library.tool_call_llm(
        connected_nodes={rng_node},
        pretty_name="Math Node",
        system_message=system_message,
        model=rc.llm.OpenAILLM("gpt-4o"),
        output_type="MessageHistory",
    )

    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as runner:
        message_history = rc.llm.MessageHistory(
            [rc.llm.UserMessage("Start the Math node.")]
        )
        response = await runner.run(math_node, message_history=message_history)
        assert any(
            message.role == "tool"
            and "There was an error running the tool" not in message.content
            for message in response.answer
        )

@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_terminal_llm_tool_with_invalid_parameters_easy_usage(model, encoder_system_message):
    # Test case where tool is invoked with incorrect parameters
    encoder_tool_details = "A tool used to encode text into bytes."
    encoder_tool_params = {
        rc.llm.Parameter("text_input", "string", "The string to encode.")
    }

    encoder = rc.library.terminal_llm(
        pretty_name="Encoder",
        system_message=encoder_system_message,
        model=model,
        tool_details=encoder_tool_details,
        tool_params=encoder_tool_params,
    )

    system_message = rc.llm.SystemMessage(
        "You are a helful assitant. Use the encoder tool with invalid parameters (invoke the tool with invalid parameters) once and then invoke it again with valid parameters."
    )
    tool_call_llm = rc.library.tool_call_llm(
        connected_nodes={encoder},
        model=model,
        pretty_name="InvalidToolCaller",
        output_type="MessageHistory",
        system_message=system_message,
    )

    with rc.Runner(
        executor_config=rc.ExecutorConfig(logging_setting="VERBOSE")
    ) as runner:
        message_history = rc.llm.MessageHistory(
            [rc.llm.UserMessage("Encode this text but use an invalid parameter name.")]
        )
        response = await runner.run(tool_call_llm, message_history=message_history)
        # Check that there was an error running the tool
        assert any(
            message.role == "tool" and "There was an error running the tool" in message.content.result
            for message in response.answer
        )


# ====================================================== END terminal_llm as tool ========================================================
