from copy import deepcopy
from typing import Dict, Any

import pytest
import requestcompletion as rc

from requestcompletion.exceptions import NodeCreationError
from requestcompletion.llm import MessageHistory, UserMessage

from requestcompletion.nodes.library import from_function

NODE_INIT_METHODS = ["easy_wrapper", "class_based"]


# =========================================== START BASE FUNCTIONALITY TESTS ===========================================
@pytest.mark.asyncio
async def test_empty_connected_nodes_easy_wrapper(model):
    """Test when the output model is empty while making a node with easy wrapper."""
    with pytest.raises(NodeCreationError, match="connected_nodes must not return an empty set."):
        _ = rc.library.tool_call_llm(
            connected_nodes=set(),
            system_message=rc.llm.SystemMessage(
                "You are a helpful assistant that can strucure the response into a structured output."
            ),
            model=model,
            pretty_name="ToolCallLLM",
        )


@pytest.mark.asyncio
async def test_empty_connected_nodes_class_based(model):
    """Test when the output model is empty while making a node with class based."""

    with pytest.raises(NodeCreationError, match="connected_nodes must not return an empty set."):

        system_simple = rc.llm.SystemMessage(
            "Return a simple text and number. Don't use any tools."
        )
        class SimpleNode(rc.library.ToolCallLLM):
            def __init__(
                self,
                message_history: rc.llm.MessageHistory,
                llm_model: rc.llm.ModelBase = model,
            ):
                message_history = [x for x in message_history if x.role != "system"]
                message_history.insert(0, system_simple)
                super().__init__(
                    message_history=message_history,
                    model=llm_model,
                )

            @classmethod
            def connected_nodes(cls):
                return {}

            @classmethod
            def pretty_name(cls) -> str:
                return "Simple Node"


@pytest.mark.asyncio
async def test_simple_function_passed_tool_call(simple_function_taking_node, simple_output_model):
    """Test the functionality of a ToolCallLLM node (using actual tools) with a structured output model."""
    with rc.Runner(executor_config=rc.ExecutorConfig(timeout=50, logging_setting="QUIET")) as runner:
        message_history = rc.llm.MessageHistory(
            [
                rc.llm.UserMessage(
                    "give me a number between 1 and 100 please as well"
                )
            ]
        )
        response = await runner.run(simple_function_taking_node, message_history=message_history)
        assert isinstance(response.answer, simple_output_model)
        assert isinstance(response.answer.text, str)
        assert isinstance(response.answer.number, int)

@pytest.mark.asyncio
async def test_some_functions_passed_tool_calls(some_function_taking_travel_planner_node, travel_planner_output_model):
    with rc.Runner(
        executor_config=rc.ExecutorConfig(timeout=50, logging_setting="NONE")
        ) as runner:
        message_history = rc.llm.MessageHistory(
            [
                rc.llm.UserMessage(
                    "I live in Delhi. I am going to travel to Denmark for 3 days, followed by Germany for 2 days and finally New York for 4 days. Please provide me with a budget summary for the trip in INR."
                )
            ]
        )
        response = await runner.run(some_function_taking_travel_planner_node, message_history=message_history)
        assert isinstance(response.answer, travel_planner_output_model)
        assert isinstance(response.answer.travel_plan, str)
        assert isinstance(response.answer.Total_cost, float)
        assert isinstance(response.answer.Currency, str)


@pytest.mark.asyncio
@pytest.mark.skip("Skipping test due to stochastic LLM failures.")
async def test_tool_with_llm_tool_as_input_easy_tools():
    """Test a tool that uses another LLM tool as input."""

    def secret_phrase(true_to_call: bool = True):
        return "2 foxes and a dog"

    # Define the child tool
    child_tool = rc.library.tool_call_llm(
        connected_nodes={from_function(secret_phrase)},
        pretty_name="Child Tool",
        system_message=rc.llm.SystemMessage(
            "When asked for a response, provide the output of the tool."
        ),
        model=rc.llm.OpenAILLM("gpt-4o"),
        tool_details="A tool that generates a simple response.",
        tool_params={
            rc.llm.Parameter(
                name="response_request",
                param_type="string",
                description="A sentence that requests a response.",
            )
        },
    )

    # Define the parent tool that uses the child tool
    parent_tool = rc.library.tool_call_llm(
        connected_nodes={child_tool},
        pretty_name="Parent Tool",
        system_message=rc.llm.SystemMessage(
            "Provide a response using the tool avaliable to you. Provide only the response, no additional text."
        ),
        model=rc.llm.OpenAILLM("gpt-4o"),
    )

    # Run the parent tool
    with rc.Runner(
        executor_config=rc.ExecutorConfig(logging_setting="NONE", timeout=1000)
    ) as runner:
        message_history = rc.llm.MessageHistory(
            [rc.llm.UserMessage("Give me a response.")]
        )
        response = await runner.run(parent_tool, message_history=message_history)

    assert response.answer is not None
    assert response.answer.content == "2 foxes and a dog"


@pytest.mark.asyncio
@pytest.mark.skip("Skipping test due to stochastic LLM failures.")
async def test_tool_with_llm_tool_as_input_class_easy():
    """Test a tool that uses another LLM tool as input."""

    def secret_phrase(true_to_call: bool = True):
        return "2 foxes and a dog"

    # Define the child tool
    class ChildTool(rc.library.ToolCallLLM):
        def __init__(
            self,
            message_history: rc.llm.MessageHistory,
        ):
            message_history_copy = deepcopy(message_history)
            message_history_copy.insert(
                0,
                rc.llm.SystemMessage(
                    "When asked for a response, provide the output of the tool."
                ),
            )

            super().__init__(
                message_history=message_history_copy, model=rc.llm.OpenAILLM("gpt-4o")
            )

        @classmethod
        def connected_nodes(cls):
            return {rc.library.from_function(secret_phrase)}

        @classmethod
        def tool_info(cls) -> rc.llm.Tool:
            return rc.llm.Tool(
                name="Child_Tool",
                detail="A tool that generates a simple response.",
                parameters={
                    rc.llm.Parameter(
                        name="response_request",
                        param_type="string",
                        description="A sentence that requests a response.",
                    )
                },
            )

        @classmethod
        def prepare_tool(cls, tool_parameters: Dict[str, Any]):
            message_hist = MessageHistory(
                [
                    UserMessage(
                        f"response_request: '{tool_parameters['response_request']}'"
                    )
                ]
            )
            return cls(message_hist)

        @classmethod
        def pretty_name(cls) -> str:
            return "Child Tool"

    # Define the parent tool that uses the child tool
    parent_tool = rc.library.tool_call_llm(
        connected_nodes={ChildTool},
        pretty_name="Parent_Tool",
        system_message=rc.llm.SystemMessage(
            "Provide a response using the tool avaliable to you. Provide only the response, no additional text."
        ),
        model=rc.llm.OpenAILLM("gpt-4o"),
    )

    # Run the parent tool
    with rc.Runner(
        executor_config=rc.ExecutorConfig(logging_setting="NONE", timeout=1000)
    ) as runner:
        message_history = rc.llm.MessageHistory(
            [rc.llm.UserMessage("Give me a response.")]
        )
        response = await runner.run(parent_tool, message_history=message_history)

    assert response.answer is not None
    assert "2 foxes and a dog" in response.answer.content


@pytest.mark.asyncio
@pytest.mark.skip("Skipping test due to stochastic LLM failures.")
async def test_tool_with_llm_tool_as_input_easy_class():
    """Test a tool that uses another LLM tool as input."""

    def secret_phrase(true_to_call: bool = True):
        return "2 foxes and a dog"

    # Define the child tool
    child_tool = rc.library.tool_call_llm(
        connected_nodes={from_function(secret_phrase)},
        pretty_name="Child_Tool",
        system_message=rc.llm.SystemMessage(
            "When asked for a response, provide the output of the tool."
        ),
        model=rc.llm.OpenAILLM("gpt-4o"),
        tool_details="A tool that generates a simple response.",
        tool_params={
            rc.llm.Parameter(
                name="response_request",
                param_type="string",
                description="A sentence that requests a response.",
            )
        },
    )

    # Define the parent tool that uses the child tool
    class ParentTool(rc.library.ToolCallLLM):
        def return_output(self):
            return self.message_hist[-1]

        def __init__(
            self,
            message_history: rc.llm.MessageHistory,
        ):
            message_history_copy = deepcopy(message_history)
            message_history_copy.insert(
                0,
                rc.llm.SystemMessage(
                    "Provide a response using the tool avaliable to you. Provide only the response, no additional text."
                ),
            )

            super().__init__(
                message_history=message_history_copy, model=rc.llm.OpenAILLM("gpt-4o")
            )

        @classmethod
        def connected_nodes(cls):
            return {child_tool}

        @classmethod
        def pretty_name(cls) -> str:
            return "Parent Tool"

    # Run the parent tool
    with rc.Runner(
        executor_config=rc.ExecutorConfig(logging_setting="NONE", timeout=1000)
    ) as runner:
        message_history = rc.llm.MessageHistory(
            [rc.llm.UserMessage("Give me a response.")]
        )
        response = await runner.run(ParentTool, message_history=message_history)

    assert response.answer is not None
    assert response.answer.content == "2 foxes and a dog"


@pytest.mark.asyncio
@pytest.mark.skip("Skipping test due to stochastic LLM failures.")
async def test_tool_with_llm_tool_as_input_class_tools():
    """Test a tool that uses another LLM tool as input."""

    def secret_phrase(true_to_call: bool = True):
        return "2 foxes and a dog"

    # Define the child tool
    class ChildTool(rc.library.ToolCallLLM):
        def __init__(
            self,
            message_history: rc.llm.MessageHistory,
        ):
            message_history_copy = deepcopy(message_history)
            message_history_copy.insert(
                0,
                rc.llm.SystemMessage(
                    "When asked for a response, provide the output of the tool."
                ),
            )

            super().__init__(
                message_history=message_history_copy, model=rc.llm.OpenAILLM("gpt-4o")
            )

        @classmethod
        def connected_nodes(cls):
            return {rc.library.from_function(secret_phrase)}

        @classmethod
        def tool_info(cls) -> rc.llm.Tool:
            return rc.llm.Tool(
                name="Child_Tool",
                detail="A tool that generates a simple response.",
                parameters={
                    rc.llm.Parameter(
                        name="response_request",
                        param_type="string",
                        description="A sentence that requests a response.",
                    )
                },
            )

        @classmethod
        def prepare_tool(cls, tool_parameters: Dict[str, Any]):
            message_hist = MessageHistory(
                [
                    UserMessage(
                        f"response_request: '{tool_parameters['response_request']}'"
                    )
                ]
            )
            return cls(message_hist)

        @classmethod
        def pretty_name(cls) -> str:
            return "Child Tool"

    # Define the parent tool that uses the child tool
    class ParentTool(rc.library.ToolCallLLM):
        def return_output(self):
            return self.message_hist[-1]

        def __init__(
            self,
            message_history: rc.llm.MessageHistory,
        ):
            message_history_copy = deepcopy(message_history)
            message_history_copy.insert(
                0,
                rc.llm.SystemMessage(
                    "Provide a response using the tool avalaible to you. Provide only the response, no additional text."
                ),
            )

            super().__init__(
                message_history=message_history_copy, model=rc.llm.OpenAILLM("gpt-4o")
            )

        @classmethod
        def connected_nodes(cls):
            return {ChildTool}

        @classmethod
        def pretty_name(cls) -> str:
            return "Parent Tool"

    # Run the parent tool
    with rc.Runner(
        executor_config=rc.ExecutorConfig(logging_setting="NONE", timeout=1000)
    ) as runner:
        message_history = rc.llm.MessageHistory(
            [rc.llm.UserMessage("Give me a response.")]
        )
        response = await runner.run(ParentTool, message_history=message_history)

    assert response.answer is not None
    assert response.answer.content == "2 foxes and a dog"

# =========================================== END BASE FUNCTIONALITY TESTS ===========================================

# =========================================== START TESTS FOR MAX TOOL CALLS ===========================================
@pytest.mark.asyncio
@pytest.mark.parametrize("class_based", [True, False], ids=["class_based", "easy_usage_wrapper"])
async def test_allows_only_one_toolcall(limited_tool_call_node_factory, travel_message_history, reset_tools_called, class_based):
    node = limited_tool_call_node_factory(max_tool_calls=1, class_based=class_based)
    message_history = travel_message_history()
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as runner:
        reset_tools_called()
        response = await rc.call(node, message_history=message_history)
        if class_based:
            assert isinstance(response, str)
        else:
            assert isinstance(response.content, str)
        assert rc.context.get("tools_called") == 1

@pytest.mark.asyncio
@pytest.mark.parametrize("class_based", [True, False], ids=["class_based", "easy_usage_wrapper"])
async def test_zero_tool_calls_forces_final_answer(limited_tool_call_node_factory, travel_message_history, reset_tools_called, class_based):
    node = limited_tool_call_node_factory(max_tool_calls=0, class_based=class_based)
    message_history = travel_message_history("Plan a trip to Paris for 2 days.")
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as runner:
        reset_tools_called()
        response = await rc.call(node, message_history=message_history)
        if class_based:
            assert isinstance(response, str)
        else:
            assert isinstance(response.content, str)
        assert rc.context.get("tools_called") == 0

@pytest.mark.asyncio
@pytest.mark.parametrize("class_based", [True, False], ids=["class_based", "easy_usage_wrapper"])
async def test_multiple_tool_calls_limit(limited_tool_call_node_factory, travel_message_history, reset_tools_called, class_based):
    node = limited_tool_call_node_factory(max_tool_calls=5, class_based=class_based)
    message_history = travel_message_history("Plan a trip to Paris, Berlin, and New York for 2 days each.")
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as runner:
        reset_tools_called()
        response = await rc.call(node, message_history=message_history)
        if class_based:
            assert isinstance(response, str)
        else:
            assert isinstance(response.content, str)
        assert rc.context.get("tools_called") <= 5

@pytest.mark.asyncio
@pytest.mark.parametrize("class_based", [True, False], ids=["class_based", "easy_usage_wrapper"])
async def test_context_reset_between_runs(limited_tool_call_node_factory, travel_message_history, reset_tools_called, class_based):
    @rc.to_node
    def magic_number():
        #  incrementing count for testing purposes
        count = rc.context.get("tools_called", -1)
        rc.context.put("tools_called", count + 1)
        return 42
    
    node = limited_tool_call_node_factory(max_tool_calls=1, class_based=class_based, tools=[magic_number])
    message_history = travel_message_history("Get the magic number and divide it by 2.")
    with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="NONE")) as runner:
        reset_tools_called()
        response = await rc.call(node, message_history=message_history)
        assert rc.context.get("tools_called") == 1
        reset_tools_called()
        response2 = await rc.call(node, message_history=message_history)
        assert rc.context.get("tools_called") == 1

# =========================================== END TESTS FOR MAX TOOL CALLS ===========================================
