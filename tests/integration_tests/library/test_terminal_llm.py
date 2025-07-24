import pytest
import railtracks as rt
from pydantic import BaseModel

from railtracks.llm import MessageHistory, Message
from railtracks.llm.response import Response
from railtracks.nodes.library.easy_usage_wrappers.terminal_llm import terminal_llm
from tests.unit_tests.llm.conftest import MockLLM


# ================================================ START terminal_llm basic functionality =========================================================
@pytest.mark.asyncio
async def test_terminal_llm_easy_usage_run(model , encoder_system_message):
    encoder_agent = rt.library.terminal_llm(
        pretty_name="Encoder",
        system_message=encoder_system_message,
        llm_model=model,
    )

    response = await rt.call(encoder_agent, user_input=rt.llm.MessageHistory([rt.llm.UserMessage("hello world")]))

    assert isinstance(response, str)

def test_terminal_llm_class_based_run(model , encoder_system_message):
    class Encoder(rt.library.TerminalLLM):
        def __init__(
                self,
                user_input: rt.llm.MessageHistory,
                llm_model: rt.llm.ModelBase = model,
            ):
                user_input = [x for x in user_input if x.role != "system"]
                user_input.insert(0, encoder_system_message)
                super().__init__(
                    user_input=user_input,
                    llm_model=model,
                )
        @classmethod
        def pretty_name(cls) -> str:
            return "Simple Node"
        
    with rt.Runner(executor_config=rt.ExecutorConfig(logging_setting="NONE")) as runner:
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("The input string is 'hello world'")]
        )
        response = runner.run_sync(Encoder, user_input=message_history)
        assert isinstance(response.answer, str)

def test_return_into():
    """Test that a node can return its result into context instead of returning it directly."""

    def return_message(messages: MessageHistory) -> Response:
        return Response(message=Message(role="assistant", content=messages[-1].content))

    node = terminal_llm(
        system_message="Hello",
        llm_model=MockLLM(chat=return_message),
        return_into="greeting"  # Specify that the result should be stored in context under the key "greeting"
    )

    with rt.Runner() as run:
        result = run.run_sync(node, user_input=MessageHistory()).answer
        assert result is None  # The result should be None since it was stored in context
        assert rt.context.get("greeting") == "Hello"

@pytest.mark.asyncio
async def test_terminal_llm_easy_usage_with_string(model, encoder_system_message):
    """Test that the easy usage wrapper can be called with a string input."""
    encoder_agent = rt.library.terminal_llm(
        pretty_name="Encoder",
        system_message=encoder_system_message,
        llm_model=model,
    )

    # Call with a string instead of MessageHistory
    response = await rt.call(encoder_agent, user_input="hello world")

    assert isinstance(response, str)

@pytest.mark.asyncio
async def test_terminal_llm_easy_usage_with_user_message(model, encoder_system_message):
    """Test that the easy usage wrapper can be called with a UserMessage input."""
    encoder_agent = rt.library.terminal_llm(
        pretty_name="Encoder",
        system_message=encoder_system_message,
        llm_model=model,
    )

    # Call with a UserMessage instead of MessageHistory
    user_msg = rt.llm.UserMessage("hello world")
    response = await rt.call(encoder_agent, user_input=user_msg)

    assert isinstance(response, str)

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

    encoder = rt.library.terminal_llm(
        pretty_name="Encoder",
        system_message=encoder_system_message,
        llm_model=model,
        # tool_details and tool_parameters are required if you want to use the terminal_llm as a tool
        tool_details=encoder_tool_details,
        tool_params=encoder_tool_params,
    )
    decoder = rt.library.terminal_llm(
        pretty_name="Decoder",
        system_message=decoder_system_message,
        llm_model=model,
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
    encoder_params = encoder.tool_info().parameters
    decoder_params = decoder.tool_info().parameters
    
    assert all(isinstance(param, rt.llm.Parameter) for param in encoder_params), (
        f"Encoder parameters {encoder_params} should be instances of rc.llm.Parameter"
    )
    
    assert all(isinstance(param, rt.llm.Parameter) for param in decoder_params), (
        f"Decoder parameters {decoder_params} should be instances of rc.llm.Parameter"
    )

    randomizer = rt.library.message_hist_tool_call_llm(
        connected_nodes={encoder, decoder},
        llm_model=model,
        pretty_name="Randomizer",
        system_message=system_randomizer,
    )

    with rt.Runner(executor_config=rt.ExecutorConfig(logging_setting="NONE")) as runner:
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("The input string is 'hello world'")]
        )
        response = await runner.run(randomizer, user_input=message_history)
        assert any(
            message.role == "tool"
            and "There was an error running the tool" not in message.content
            for message in response.answer
        )  # inside tool_call_llm's invoke function is this exact string in case of error


@pytest.mark.asyncio
async def test_terminal_llm_as_tool_correct_initialization_no_params(model):

    rng_tool_details = "A tool that generates 5 random integers between 1 and 100."

    rng_node = rt.library.terminal_llm(
        pretty_name="RNG Tool",
        system_message="You are a helful assistant that can generate 5 random numbers between 1 and 100.",
        llm_model=model,
        tool_details=rng_tool_details,
        tool_params=None,
    )

    assert rng_node.tool_info().name == "RNG_Tool"
    assert rng_node.tool_info().detail == rng_tool_details
    assert rng_node.tool_info().parameters is None

    system_message = "You are a math genius that calls the RNG tool to generate 5 random numbers between 1 and 100 and gives the sum of those numbers."

    math_node = rt.library.message_hist_tool_call_llm(
        connected_nodes={rng_node},
        pretty_name="Math Node",
        system_message=system_message,
        llm_model=rt.llm.OpenAILLM("gpt-4o"),
    )

    with rt.Runner(executor_config=rt.ExecutorConfig(logging_setting="NONE")) as runner:
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Start the Math node.")]
        )
        response = await runner.run(math_node, user_input=message_history)
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
        rt.llm.Parameter("text_input", "string", "The string to encode.")
    }

    encoder = rt.library.terminal_llm(
        pretty_name="Encoder",
        system_message=encoder_system_message,
        llm_model=model,
        tool_details=encoder_tool_details,
        tool_params=encoder_tool_params,
    )

    system_message = "You are a helful assitant. Use the encoder tool with invalid parameters (invoke the tool with invalid parameters) once and then invoke it again with valid parameters."
    tool_call_llm = rt.library.message_hist_tool_call_llm(
        connected_nodes={encoder},
        llm_model=model,
        pretty_name="InvalidToolCaller",
        system_message=system_message,
    )

    with rt.Runner(
        executor_config=rt.ExecutorConfig(logging_setting="VERBOSE")
    ) as runner:
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Encode this text but use an invalid parameter name.")]
        )
        response = await runner.run(tool_call_llm, user_input=message_history)
        # Check that there was an error running the tool
        assert any(
            message.role == "tool" and "There was an error running the tool" in message.content.result
            for message in response.answer
        )


# ====================================================== END terminal_llm as tool ========================================================
