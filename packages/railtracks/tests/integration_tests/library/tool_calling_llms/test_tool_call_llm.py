from copy import deepcopy
from typing import Dict, Any

import pytest

import railtracks
import railtracks as rt

from railtracks.exceptions import NodeCreationError
from railtracks.llm import MessageHistory, UserMessage, Message
from railtracks.llm.response import Response

from railtracks import function_node
from railtracks.nodes.concrete import ToolCallLLM
from railtracks.nodes.easy_usage_wrappers.helpers import tool_call_llm

NODE_INIT_METHODS = ["easy_wrapper", "class_based"]


# =========================================== START BASE FUNCTIONALITY TESTS ===========================================
@pytest.mark.asyncio
async def test_empty_connected_nodes_easy_wrapper(mock_llm):
    """Test when the output model is empty while making a node with easy wrapper."""
    with pytest.raises(NodeCreationError, match="tool_nodes must not return an empty set."):
        _ = tool_call_llm(
            tool_nodes=set(),
            system_message="You are a helpful assistant that can strucure the response into a structured output.",
            llm_model=mock_llm,
            name="ToolCallLLM",
        )


@pytest.mark.asyncio
async def test_empty_connected_nodes_class_based(mock_llm):
    """Test when the output model is empty while making a node with class based."""

    with pytest.raises(NodeCreationError, match="tool_nodes must not return an empty set."):

        system_simple ="Return a simple text and number. Don't use any tools."
        class SimpleNode(ToolCallLLM):
            def __init__(
                self,
                user_input: rt.llm.MessageHistory,
                llm_model: rt.llm.ModelBase = mock_llm(),
            ):
                user_input = [x for x in user_input if x.role != "system"]
                user_input.insert(0, system_simple)
                super().__init__(
                    user_input=MessageHistory(user_input),
                    llm_model=llm_model,
                )

            @classmethod
            def tool_nodes(cls):
                return {}

            @classmethod
            def name(cls) -> str:
                return "Simple Node"


@pytest.mark.asyncio
async def test_simple_function_passed_tool_call(simple_function_taking_node, simple_output_model):
    """Test the functionality of a ToolCallLLM node (using actual tools) with a structured output model."""
    with rt.Session(timeout=50, logging_setting="QUIET") as runner:
        message_history = rt.llm.MessageHistory(
            [
                rt.llm.UserMessage(
                    "give me a number between 1 and 100 please as well"
                )
            ]
        )
        response = await rt.call(simple_function_taking_node, user_input=message_history)
        assert isinstance(response.structured, simple_output_model)
        assert isinstance(response.structured.text, str)
        assert isinstance(response.structured.number, int)

@pytest.mark.asyncio
async def test_some_functions_passed_tool_calls(some_function_taking_travel_planner_node, travel_planner_output_model):
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
        response = await rt.call(some_function_taking_travel_planner_node, user_input=message_history)
        assert isinstance(response.structured, travel_planner_output_model)
        assert isinstance(response.structured.travel_plan, str)
        assert isinstance(response.structured.Total_cost, float)
        assert isinstance(response.structured.Currency, str)


def test_return_into(mock_llm):
    """Test that a node can return its result into context instead of returning it directly."""

    def return_message(messages: MessageHistory, list) -> Response:
        return Response(message=Message(role="assistant", content="Hello"))

    node = tool_call_llm(
        system_message="Hello",
        tool_nodes={return_message},
        llm_model=mock_llm(chat_with_tools=return_message),
        return_into="greeting"  # Specify that the result should be stored in context under the key "greeting"
    )

    with rt.Session() as run:
        result = rt.call_sync(node, user_input=MessageHistory())
        assert result is None  # The result should be None since it was stored in context
        assert rt.context.get("greeting").content == "Hello"


def test_return_into_custom_fn(mock_llm):
    """Test that a node can return its result into context instead of returning it directly."""
    def format_function(value: Any) -> str:
        """Custom function to format the value before storing it in context."""
        railtracks.context.put("greeting", value.content.upper())
        return "Success!"

    def return_message(messages: MessageHistory, list) -> Response:
        return Response(message=Message(role="assistant", content="Hello"))

    node = tool_call_llm(
        system_message="Hello",
        tool_nodes={return_message},
        llm_model=mock_llm(chat_with_tools=return_message),
        return_into="greeting",  # Specify that the result should be stored in context under the key "greeting"
        format_for_return=format_function  # Use the custom formatting function
    )

    with rt.Session() as run:
        result = rt.call_sync(node, user_input=MessageHistory())
        assert result == "Success!"  # The result should be None since it was stored in context
        assert rt.context.get("greeting") == "HELLO"

# =========================================== END BASE FUNCTIONALITY TESTS ===========================================

# =========================================== START TESTS FOR MAX TOOL CALLS ===========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("class_based", [True, False], ids=["class_based", "easy_usage_wrapper"])
async def test_allows_only_one_toolcall(limited_tool_call_node_factory, travel_message_history, reset_tools_called, class_based):
    node = limited_tool_call_node_factory(max_tool_calls=1, class_based=class_based)
    message_history = travel_message_history()
    with rt.Session(logging_setting="NONE") as runner:
        reset_tools_called()
        response = await rt.call(node, user_input=message_history)
        assert isinstance(response.content, str)
        assert rt.context.get("tools_called") == 1

@pytest.mark.asyncio
@pytest.mark.parametrize("class_based", [True, False], ids=["class_based", "easy_usage_wrapper"])
async def test_zero_tool_calls_forces_final_answer(limited_tool_call_node_factory, travel_message_history, reset_tools_called, class_based):
    node = limited_tool_call_node_factory(max_tool_calls=0, class_based=class_based)
    message_history = travel_message_history("Plan a trip to Paris for 2 days.")
    with rt.Session(logging_setting="NONE") as runner:
        reset_tools_called()
        response = await rt.call(node, user_input=message_history)
        assert isinstance(response.content, str)
        assert rt.context.get("tools_called") == 0

@pytest.mark.asyncio
@pytest.mark.parametrize("class_based", [True, False], ids=["class_based", "easy_usage_wrapper"])
async def test_multiple_tool_calls_limit(limited_tool_call_node_factory, travel_message_history, reset_tools_called, class_based):
    node = limited_tool_call_node_factory(max_tool_calls=5, class_based=class_based)
    message_history = travel_message_history("Plan a trip to Paris, Berlin, and New York for 2 days each.")
    with rt.Session(logging_setting="NONE") as runner:
        reset_tools_called()
        response = await rt.call(node, user_input=message_history)
        assert isinstance(response.content, str)
        assert rt.context.get("tools_called") <= 5

@pytest.mark.asyncio
@pytest.mark.parametrize("class_based", [True, False], ids=["class_based", "easy_usage_wrapper"])
async def test_context_reset_between_runs(limited_tool_call_node_factory, travel_message_history, reset_tools_called, class_based):
    @rt.function_node
    def magic_number():
        #  incrementing count for testing purposes
        count = rt.context.get("tools_called", -1)
        rt.context.put("tools_called", count + 1)
        return 42
    
    node = limited_tool_call_node_factory(max_tool_calls=1, class_based=class_based, tools=[magic_number])
    message_history = travel_message_history("Get the magic number and divide it by 2.")
    with rt.Session(logging_setting="NONE") as runner:
        reset_tools_called()
        response = await rt.call(node, user_input=message_history)
        assert rt.context.get("tools_called") == 1
        reset_tools_called()
        response2 = await rt.call(node, user_input=message_history)
        assert rt.context.get("tools_called") == 1

# =========================================== END TESTS FOR MAX TOOL CALLS ===========================================
