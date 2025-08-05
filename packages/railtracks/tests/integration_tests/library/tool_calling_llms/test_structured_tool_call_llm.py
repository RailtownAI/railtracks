import pytest
import railtracks as rt

from railtracks.llm import Message, MessageHistory
from railtracks.llm.response import Response

from pydantic import BaseModel

from railtracks.nodes.easy_usage_wrappers.helpers import structured_llm, tool_call_llm, structured_tool_call_llm

NODE_INIT_METHODS = ["easy_wrapper", "class_based"]


@pytest.mark.asyncio
@pytest.mark.parametrize("simple_node", NODE_INIT_METHODS, indirect=True)
async def test_structured_with_no_tool_calls(simple_node, simple_output_model):
    """Test basic functionality of returning a structured output."""
    with rt.Session(logging_setting="NONE") as runner:
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Generate a simple text and number.")]
        )
        response = await rt.call(simple_node, user_input=message_history)
        assert isinstance(response.structured, simple_output_model)
        assert isinstance(response.structured.text, str)
        assert isinstance(response.structured.number, int)

@pytest.mark.asyncio
@pytest.mark.skip("Skipping test due to stochastic LLM failures.")
async def test_tool_with_structured_output_child_tool():
    """Test a tool that uses another LLM tool with structured output as input."""

    # Define a structured output model
    class ChildResponse(BaseModel):
        message: str
        word_count: int

    class ParentResponse(BaseModel):
        message: str
        word_count: int
        success: bool

    # Define the child tool with structured output
    child_tool = structured_llm(
        output_schema=ChildResponse,
        system_message="You are a word counting tool that counts the number of words in the request provided by the user.",
        llm_model=rt.llm.OpenAILLM("gpt-4o"),
        name="Structured Child Tool",
        tool_details="A tool that generates a structured response that includes word count.",
        tool_params={
            rt.llm.Parameter(
                name="request",
                param_type="string",
                description="A sentence to generate a response for.",
            )
        },
    )

    # Define the parent tool that uses the child tool
    parent_tool = structured_tool_call_llm(
        output_schema=ParentResponse,
        tool_nodes={child_tool},
        name="Parent Tool",
        system_message="Use the child tool to generate a structured response. Respond with the output from the child tool only. No additional text.",
        llm_model=rt.llm.OpenAILLM("gpt-4o"),
    )

    # Run the parent tool
    with rt.Session(
       logging_setting="NONE", timeout=1000
    ) as runner:
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Generate a structured response for 'Hello World'.")]
        )
        response = await rt.call(parent_tool, user_input=message_history)

    # Assertions
    assert response is not None
    assert isinstance(response, ParentResponse)
    assert response.message == "Hello World"
    assert response.word_count == 2
    assert response.success is True

@pytest.mark.asyncio
async def test_functions_passed_tool_calls(only_function_taking_travel_planner_node, travel_planner_output_model):
    """Test the functionality of a ToolCallLLM node (using actual tools) with a structured output model."""
    with rt.Session(timeout=50, logging_setting="QUIET") as runner:
        message_history = rt.llm.MessageHistory(
            [
                rt.llm.UserMessage(
                    "I live in Delhi. I am going to travel to Denmark for 3 days, followed by Germany for 2 days and finally New York for 4 days. Please provide me with a budget summary for the trip in INR."
                )
            ]
        )
        response = await rt.call(only_function_taking_travel_planner_node, user_input=message_history)
        assert isinstance(response.structured, travel_planner_output_model)
        assert isinstance(response.structured.travel_plan, str)
        assert isinstance(response.structured.Total_cost, float)
        assert isinstance(response.structured.Currency, str)

@pytest.mark.asyncio
@pytest.mark.parametrize("math_node", NODE_INIT_METHODS, indirect=True)
async def test_structured_with_terminal_llm_as_tool(math_node, math_output_model):
    """Test the functionality of a ToolCallLLM node (using terminalLLM as tool) with a structured output model."""
    with rt.Session(logging_setting="NONE") as runner:
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Start the Math node.")]
        )
        response = await rt.call(math_node, user_input=message_history)
        assert isinstance(response.structured, math_output_model)
        assert isinstance(response.structured.sum, float)
        assert isinstance(response.structured.random_numbers, list)


@pytest.mark.asyncio
@pytest.mark.parametrize("complex_node", NODE_INIT_METHODS, indirect=True)
async def test_structured_with_complex_output_model(
    complex_node, person_output_model, simple_output_model
):
    """Test the functionality of structured output model with complex output model."""
    with rt.Session(logging_setting="NONE") as runner:
        message_history = rt.llm.MessageHistory(
            [
                rt.llm.UserMessage(
                    "My name is John Doe. I am 30 years old. My favourite text is 'Hello World' and my favourite number is 1290."
                )
            ]
        )
        response = await rt.call(complex_node, user_input=message_history)
        assert isinstance(response.structured, person_output_model)
        assert isinstance(response.structured.name, str)
        assert isinstance(response.structured.age, int)
        assert isinstance(response.structured.Favourites, simple_output_model)
        assert isinstance(response.structured.Favourites.text, str)
        assert isinstance(response.structured.Favourites.number, int)


@pytest.mark.asyncio
@pytest.mark.parametrize("travel_planner_node", NODE_INIT_METHODS, indirect=True)
async def test_structured_with_tool_calls(
    travel_planner_node, travel_planner_output_model
):
    """Test the functionality of a ToolCallLLM node (using actual tools) with a structured output model."""
    with rt.Session(
       timeout=50, logging_setting="NONE"
    ) as runner:
        message_history = rt.llm.MessageHistory(
            [
                rt.llm.UserMessage(
                    "I live in Delhi. I am going to travel to Denmark for 3 days, followed by Germany for 2 days and finally New York for 4 days. Please provide me with a budget summary for the trip in INR."
                )
            ]
        )

        response = await rt.call(
            travel_planner_node, user_input=message_history
        )
        assert isinstance(response.structured, travel_planner_output_model)
        assert isinstance(response.structured.travel_plan, str)
        assert isinstance(response.structured.Total_cost, float)
        assert isinstance(response.structured.Currency, str)


def test_return_into_structured(mock_llm):
    """Test that a node can return its structured result into context instead of returning it directly."""

    class StructuredModel(BaseModel):
        text: str
        number: int

    def return_structured_message(messages: MessageHistory, basemodel) -> Response:
        return Response(message=Message(role="assistant", content=basemodel(text="Hello", number=42)))

    node = structured_llm(
        system_message="Hello",
        llm_model=mock_llm(structured=return_structured_message),
        return_into="structured_greeting",  # Store result in context
        output_schema=StructuredModel,
    )

    with rt.Session() as run:
        result = rt.call_sync(node, user_input=MessageHistory())
        assert result is None  # The result should be None since it was stored in context
        stored = rt.context.get("structured_greeting")
        assert stored is not None
        assert stored.text == "Hello"
        assert stored.number == 42
