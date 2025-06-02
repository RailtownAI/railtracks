import pytest
from copy import deepcopy
import src.requestcompletion as rc

NODE_INIT_METHODS = ["class_based", "easy_wrapper"]

@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_nodes", NODE_INIT_METHODS, indirect=True)
async def test_message_history_not_mutated_terminal_llm(model, terminal_nodes):
    """
    Verify that message history is not modified after rc.call when passed to nodes constructed using different methods.
    """
    rng_node, rng_operation_node, math_detective_node = terminal_nodes  # All nodes can be found in ./conftest.py
    
    # Determine if we need to pass the model based on which fixture was used
    needs_model = isinstance(terminal_nodes, tuple) and any(hasattr(node, '__call__') and node.__name__ == "TerminalLLMNode" for node in terminal_nodes)

    async def make_math_game_node(message_history: rc.llm.MessageHistory):
        original_message_history = deepcopy(message_history)

        # Common parameters for node calls
        call_params = {"message_history": message_history}
        if needs_model:
            call_params["llm_model"] = model

        # First node call
        random_num_list_response = await rc.call(rng_node, **call_params)
        assert all(orig.content == new.content for orig, new in zip(original_message_history, message_history)), "Message history modified after rc.call 1"

        message_history.append(rc.llm.AssistantMessage("The list of random integer: " + str(random_num_list_response)))
        original_message_history.append(rc.llm.AssistantMessage("The list of random integer: " + str(random_num_list_response)))

        # Second node call
        operation_response = await rc.call(rng_operation_node, **call_params)
        assert all(orig.content == new.content for orig, new in zip(original_message_history, message_history)), "Message history modified after rc.call 2"

        message_history.append(rc.llm.AssistantMessage("The result int (x) = " + str(operation_response)))
        original_message_history.append(rc.llm.AssistantMessage("The result int (x) = " + str(operation_response)))

        # Third node call
        response = await rc.call(math_detective_node, **call_params)
        assert all(orig.content == new.content for orig, new in zip(original_message_history, message_history)), "Message history modified after rc.call 3"

        return response

    MathGameNode = rc.library.from_function(make_math_game_node)

    with rc.Runner() as runner:
        message_history = rc.llm.MessageHistory([rc.llm.UserMessage("You can start the game")])
        original_message_history = deepcopy(message_history)
        _ = await runner.run(MathGameNode, message_history=message_history)
        assert all(orig.content == new.content for orig, new in zip(original_message_history, message_history)), "Message history modified after runner run"


@pytest.mark.asyncio
@pytest.mark.parametrize("structured_nodes", NODE_INIT_METHODS, indirect=True)
async def test_message_history_not_mutated_structured_llm(model, structured_nodes):
    """
    Verify that message history is not modified after rc.call when passed to nodes constructed using different methods.
    """
    math_undergrad_student_node, math_professor_node = structured_nodes  # All nodes can be found in ./conftest.py
    
    # Determine if we need to pass the model based on which fixture was used
    needs_model = isinstance(structured_nodes, tuple) and any(hasattr(node, '__call__') and node.__name__ == "StructuredLLMNode" for node in structured_nodes)

    async def math_proof_node(message_history: rc.llm.MessageHistory):
        original_message_history = deepcopy(message_history)

        # Common parameters for node calls
        call_params = {"message_history": message_history}
        if needs_model:
            call_params["llm_model"] = model

        # First node (math student node)
        student_proof = await rc.call(math_undergrad_student_node, **call_params)
        assert all(orig.content == new.content for orig, new in zip(original_message_history, message_history)), "Message history modified after rc.call 1"

        message_history.append(rc.llm.AssistantMessage("The proof: " + student_proof.proof))
        original_message_history.append(rc.llm.AssistantMessage("The proof: " + student_proof.proof))

        # Second node call (math professor node)
        prof_grade = await rc.call(math_professor_node, **call_params)
        assert all(orig.content == new.content for orig, new in zip(original_message_history, message_history)), "Message history modified after rc.call 2"

        message_history.append(rc.llm.AssistantMessage("The grade: " + str(prof_grade.overall_score)))
        message_history.append(rc.llm.AssistantMessage("The feedback: " + prof_grade.feedback))
        original_message_history.append(rc.llm.AssistantMessage("The grade: " + str(prof_grade.overall_score)))
        original_message_history.append(rc.llm.AssistantMessage("The feedback: " + prof_grade.feedback))

        return prof_grade

    MathProofNode = rc.library.from_function(math_proof_node)

    with rc.Runner() as runner:
        message_history = rc.llm.MessageHistory([rc.llm.UserMessage("Prove that the sum of all numbers until infinity is -1/12")])
        original_message_history = deepcopy(message_history)
        _ = await runner.run(MathProofNode, message_history=message_history)
        assert all(orig.content == new.content for orig, new in zip(original_message_history, message_history)), "Message history modified after runner run"

@pytest.mark.asyncio
@pytest.mark.parametrize("tool_calling_nodes", NODE_INIT_METHODS, indirect=True)
async def test_message_history_not_mutated_tool_call_llm(model, tool_calling_nodes):
    """
    Verify that message history is not modified after rc.call when passed to nodes constructed using different methods.
    """
    currrency_converter_node, travel_planner_node = tool_calling_nodes  # All nodes can be found in ./conftest.py
    
    # Determine if we need to pass the model based on which fixture was used
    needs_model = isinstance(tool_calling_nodes, tuple) and any(hasattr(node, '__call__') and node.__name__ == "ToolCallLLMNode" for node in tool_calling_nodes)

    async def travel_summarizer_node(message_history: rc.llm.MessageHistory):
        original_message_history = deepcopy(message_history)

        # Common parameters for node calls
        call_params = {"message_history": message_history}
        if needs_model:
            call_params["llm_model"] = model

        # First node call
        travel_planner_response = await rc.call(travel_planner_node, **call_params)
        assert all(orig.content == new.content for orig, new in zip(original_message_history, message_history)), "Message history modified after rc.call 1"

        message_history.append(rc.llm.AssistantMessage("The travel plan: " + str(travel_planner_response)))
        original_message_history.append(rc.llm.AssistantMessage("The travel plan: " + str(travel_planner_response)))

        # Second node call
        response = await rc.call(currrency_converter_node, **call_params)
        assert all(orig.content == new.content for orig, new in zip(original_message_history, message_history)), "Message history modified after rc.call 2"

        return response

    TravelSummarizerNode = rc.library.from_function(travel_summarizer_node)
    with rc.Runner() as runner:
        message_history = rc.llm.MessageHistory([rc.llm.UserMessage("I want to plan a trip to from Delhi to New York for a week. Please provide me with a budget summary for the trip.")])
        original_message_history = deepcopy(message_history)
        _ = await runner.run(TravelSummarizerNode, message_history=message_history)
        assert all(orig.content == new.content for orig, new in zip(original_message_history, message_history)), "Message history modified after runner run"
