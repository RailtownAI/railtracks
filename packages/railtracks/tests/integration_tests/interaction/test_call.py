from __future__ import annotations

import asyncio
import random
from copy import deepcopy
from typing import List

import pytest
import railtracks as rt
from railtracks.exceptions import GlobalTimeOutError
from railtracks.nodes.nodes import Node


@pytest.mark.asyncio
async def test_message_history_not_mutated_terminal_llm(terminal_nodes):
    """
    Verify that message history is not modified after rt.call when passed to nodes constructed using different methods.
    """
    rng_node, rng_operation_node, math_detective_node = (
        terminal_nodes  # All nodes can be found in ./conftest.py
    )

    async def make_math_game_node(message_history: rt.llm.MessageHistory):
        original_message_history = deepcopy(message_history)

        # Common parameters for node calls
        call_params = {"user_input": message_history}

        # First node call
        random_num_list_response = await rt.call(rng_node, **call_params)
        assert all(
            orig.content == new.content
            for orig, new in zip(original_message_history, message_history)
        ), "Message history modified after rt.call 1"

        message_history.append(
            rt.llm.AssistantMessage(
                "The list of random integer: " + str(random_num_list_response)
            )
        )
        original_message_history.append(
            rt.llm.AssistantMessage(
                "The list of random integer: " + str(random_num_list_response)
            )
        )

        # Second node call
        operation_response = await rt.call(rng_operation_node, **call_params)
        assert all(
            orig.content == new.content
            for orig, new in zip(original_message_history, message_history)
        ), "Message history modified after rt.call 2"

        message_history.append(
            rt.llm.AssistantMessage("The result int (x) = " + str(operation_response))
        )
        original_message_history.append(
            rt.llm.AssistantMessage("The result int (x) = " + str(operation_response))
        )

        # Third node call
        response = await rt.call(math_detective_node, **call_params)
        assert all(
            orig.content == new.content
            for orig, new in zip(original_message_history, message_history)
        ), "Message history modified after rt.call 3"

        return response

    MathGameNode = rt.function_node(make_math_game_node)  # noqa: N806

    with rt.Session(logging_setting="NONE"):
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("You can start the game")]
        )
        original_message_history = deepcopy(message_history)
        _ = await rt.call(MathGameNode, message_history=message_history)
        assert all(
            orig.content == new.content
            for orig, new in zip(original_message_history, message_history)
        ), "Message history modified after runner run"


@pytest.mark.asyncio
async def test_message_history_not_mutated_structured_llm(structured_nodes):
    """
    Verify that message history is not modified after rt.call when passed to nodes constructed using different methods.
    """
    math_undergrad_student_node, math_professor_node = (
        structured_nodes  # All nodes can be found in ./conftest.py
    )

    async def math_proof_node(message_history: rt.llm.MessageHistory):
        original_message_history = deepcopy(message_history)

        # Common parameters for node calls
        call_params = {"user_input": message_history}

        # First node (math student node)
        student_proof = await rt.call(math_undergrad_student_node, **call_params)
        assert all(
            orig.content == new.content
            for orig, new in zip(original_message_history, message_history)
        ), "Message history modified after rt.call 1"

        message_history.append(
            rt.llm.AssistantMessage("The proof: " + student_proof.structured.proof)
        )
        original_message_history.append(
            rt.llm.AssistantMessage("The proof: " + student_proof.structured.proof)
        )

        # Second node call (math professor node)
        prof_grade = await rt.call(math_professor_node, **call_params)
        assert all(
            orig.content == new.content
            for orig, new in zip(original_message_history, message_history)
        ), "Message history modified after rt.call 2"

        message_history.append(
            rt.llm.AssistantMessage(
                "The grade: " + str(prof_grade.structured.overall_score)
            )
        )
        message_history.append(
            rt.llm.AssistantMessage("The feedback: " + prof_grade.structured.feedback)
        )
        original_message_history.append(
            rt.llm.AssistantMessage(
                "The grade: " + str(prof_grade.structured.overall_score)
            )
        )
        original_message_history.append(
            rt.llm.AssistantMessage("The feedback: " + prof_grade.structured.feedback)
        )

        return prof_grade

    MathProofNode = rt.function_node(math_proof_node)  # noqa: N806

    with rt.Session(logging_setting="NONE"):
        message_history = rt.llm.MessageHistory(
            [
                rt.llm.UserMessage(
                    "Prove that the sum of all numbers until infinity is -1/12"
                )
            ]
        )
        original_message_history = deepcopy(message_history)
        _ = await rt.call(MathProofNode, message_history=message_history)
        assert all(
            orig.content == new.content
            for orig, new in zip(original_message_history, message_history)
        ), "Message history modified after runner run"


@pytest.mark.timeout(34)
@pytest.mark.asyncio
async def test_message_history_not_mutated_tool_call_llm(tool_calling_nodes):
    """
    Verify that message history is not modified after rt.call when passed to nodes constructed using different methods.
    """
    currrency_converter_node, travel_planner_node = (
        tool_calling_nodes  # All nodes can be found in ./conftest.py
    )

    async def travel_summarizer_node(message_history: rt.llm.MessageHistory):
        original_message_history = deepcopy(message_history)

        # Common parameters for node calls
        call_params = {"user_input": message_history}

        # First node call
        travel_planner_response = await rt.call(travel_planner_node, **call_params)
        assert all(
            orig.content == new.content
            for orig, new in zip(original_message_history, message_history)
        ), "Message history modified after rt.call 1"

        message_history.append(
            rt.llm.AssistantMessage("The travel plan: " + str(travel_planner_response))
        )
        original_message_history.append(
            rt.llm.AssistantMessage("The travel plan: " + str(travel_planner_response))
        )

        # Second node call
        response = await rt.call(currrency_converter_node, **call_params)
        assert all(
            orig.content == new.content
            for orig, new in zip(original_message_history, message_history)
        ), "Message history modified after rt.call 2"

        return response

    TravelSummarizerNode = rt.function_node(travel_summarizer_node)  # noqa: N806
    with rt.Session(logging_setting="NONE"):
        message_history = rt.llm.MessageHistory(
            [
                rt.llm.UserMessage(
                    "I want to plan a trip to from Delhi to New York for a week. Please provide me with a budget summary for the trip."
                )
            ]
        )
        original_message_history = deepcopy(message_history)
        _ = await rt.call(TravelSummarizerNode, message_history=message_history)
        assert all(
            orig.content == new.content
            for orig, new in zip(original_message_history, message_history)
        ), "Message history modified after runner run"


async def test_no_context_call():
    with pytest.raises(Exception):
        await rt.call(
            lambda: "This should not work",
            "This is a test argument",
            key="This is a test keyword argument",
        )

def add(x: float, y: float):
    """A simple synchronous function that adds two numbers."""
    return x + y


AddNode = rt.function_node(add)


async def async_add_many(pairs: list[float]):
    """An asynchronous function that adds many numbers."""
    total = 0
    for i in range(len(pairs)):
        total = await rt.call(AddNode, total, pairs[i])
    return total


AddManyAsyncNode = rt.function_node(async_add_many)


# ============================================ START Many calls and Timeout tests ============================================

RNGNode = rt.function_node(random.random)


async def many_calls(num_calls: int, parallel_calls: int):
    data = []
    for _ in range(num_calls):
        contracts = [rt.call(RNGNode) for _ in range(parallel_calls)]
        results = await asyncio.gather(*contracts)
        data.extend(results)
    return data


ManyCalls = rt.function_node(many_calls)


@pytest.mark.asyncio
async def many_calls_tester(num_calls: int, parallel_calls: int):
    with rt.Session(logging_setting="NONE") as run:
        finished_result = await rt.call(ManyCalls, num_calls, parallel_calls)
        info = run.info

    ans = finished_result

    assert isinstance(ans, list)
    assert len(ans) == num_calls * parallel_calls
    assert all(0 < x < 1 for x in ans)
    assert {x.step for x in info.all_stamps} == set(
        range(num_calls * parallel_calls * 2 + 2)
    )

    assert len(info.all_stamps) == 2 * num_calls * parallel_calls + 2


@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_no_deadlock():
    num_calls = 4
    parallel_calls = 55

    await many_calls_tester(num_calls, parallel_calls)


@pytest.mark.asyncio
async def test_small_no_deadlock():
    num_calls = 10
    parallel_calls = 15

    await many_calls_tester(num_calls, parallel_calls)


@pytest.mark.asyncio
async def test_large_no_deadlock():
    num_calls = 45
    parallel_calls = 23

    await many_calls_tester(num_calls, parallel_calls)


@pytest.mark.asyncio
async def test_simple_rng():
    with rt.Session(logging_setting="NONE"):
        result = await rt.call(RNGNode)

    assert 0 < result < 1


class NestedManyCalls(Node):
    def __init__(self, num_calls: int, parallel_calls: int, depth: int):
        self.num_calls = num_calls
        self.parallel_calls = parallel_calls
        self.depth = depth
        super().__init__()

    async def invoke(
        self,
    ):
        data = []
        for _ in range(self.num_calls):
            if self.depth == 0:
                contracts = [rt.call(RNGNode) for _ in range(self.parallel_calls)]
                results = await asyncio.gather(*contracts)

            else:
                contracts = [
                    rt.call(
                        NestedManyCalls,
                        self.num_calls,
                        self.parallel_calls,
                        self.depth - 1,
                    )
                    for _ in range(self.parallel_calls)
                ]

                results = await asyncio.gather(*contracts)
                # flatten the list here.
                results = [x for y in results for x in y]
            data.extend(results)
        return data

    @classmethod
    def name(cls) -> str:
        return "NestedManyCalls"

    @classmethod
    def type(cls):
        return "Tool"


@pytest.mark.asyncio
async def nested_many_calls_tester(num_calls: int, parallel_calls: int, depth: int):
    with rt.Session(logging_setting="NONE") as run:
        await rt.call(NestedManyCalls, num_calls, parallel_calls, depth)

    ans = run.info

    assert isinstance(ans.answer, list)
    assert len(ans.answer) == (parallel_calls * num_calls) ** (depth + 1)
    assert all(0 < x < 1 for x in ans.answer)

    r_h = ans.request_forest
    assert len(r_h.insertion_request) == 1
    child_requests = r_h.children(r_h.insertion_request[0].sink_id)

    assert len(child_requests) == num_calls * parallel_calls
    for r in child_requests:
        assert r.input[0][0] == num_calls
        assert r.input[0][1] == parallel_calls
        assert 0 < r.input[0][2] < depth


@pytest.mark.timeout(4)
@pytest.mark.asyncio
async def test_nested_no_deadlock():
    num_calls = 2
    parallel_calls = 2
    depth = 3

    await nested_many_calls_tester(num_calls, parallel_calls, depth)


@pytest.mark.asyncio
async def test_nested_no_deadlock_harder():
    num_calls = 1
    parallel_calls = 3
    depth = 3

    await nested_many_calls_tester(num_calls, parallel_calls, depth)


@pytest.mark.asyncio
async def test_nested_no_deadlock_harder_2():
    num_calls = 3
    parallel_calls = 1
    depth = 3

    await nested_many_calls_tester(num_calls, parallel_calls, depth)


@pytest.mark.asyncio
async def test_multiple_runs():
    with rt.Session(logging_setting="NONE") as run:
        result = await rt.call(RNGNode)
        assert 0 < result < 1

        result = await rt.call(RNGNode)

        info = run.info
        assert isinstance(info.answer, List)
        assert 0 < info.answer[0] < 1
        assert 0 < info.answer[1] < 1

        insertion_requests = info.request_forest.insertion_request

        assert isinstance(insertion_requests, List)
        assert len(insertion_requests) == 2
        for i_r in insertion_requests:
            i_r_id = i_r.identifier

            subset_info = info._get_info(i_r_id)
            assert 0 < subset_info.answer < 1
            assert len(subset_info.node_forest.heap()) == 1


@pytest.mark.asyncio
async def test_multiple_runs_async():
    with rt.Session(logging_setting="NONE") as run:
        result = await rt.call(RNGNode)
        assert 0 < result < 1

        result = await rt.call(RNGNode)

        result = run.info.answer
        assert isinstance(result, List)
        assert 0 < result[0] < 1
        assert 0 < result[1] < 1

        info = run.info

        insertion_requests = info.request_forest.insertion_request

        assert isinstance(insertion_requests, List)
        assert len(insertion_requests) == 2
        for i_r in insertion_requests:
            i_r_id = i_r.identifier

            subset_info = info._get_info(i_r_id)
            assert 0 < subset_info.answer < 1
            assert len(subset_info.node_forest.heap()) == 1


def level_3(message: str):
    return message


Level3 = rt.function_node(level_3)


async def a_level_2(message: str):
    return await rt.call(Level3, message)


ALevel2 = rt.function_node(a_level_2)


@pytest.mark.parametrize("level_2_node", [ALevel2], ids=["async"])
@pytest.mark.asyncio
async def test_multi_level_calls(level_2_node):
    async def level_1_async(message: str):
        return await rt.call(level_2_node, message)

    ALevel1 = rt.function_node(level_1_async)  # noqa: N806

    with rt.Session(logging_setting="NONE"):
        result = await rt.call(ALevel1, "Hello from Level 1 (async)")
        assert result == "Hello from Level 1 (async)"

    with rt.Session(logging_setting="NONE"):
        result = await rt.call(ALevel1, "Hello from Level 1 (async)")
        assert result == "Hello from Level 1 (async)"


async def timeout_node(timeout_len: float):
    """
    A node that sleeps for the given timeout length.
    """
    await asyncio.sleep(timeout_len)
    return timeout_len


TimeoutNode = rt.function_node(timeout_node)


@pytest.mark.asyncio
async def test_timeout():
    with rt.Session(logging_setting="NONE", timeout=0.1):
        with pytest.raises(GlobalTimeOutError):
            await rt.call(TimeoutNode, 0.3)


async def timeout_thrower():
    raise asyncio.TimeoutError("Test timeout error")


TimeoutThrower = rt.function_node(timeout_thrower)


@pytest.mark.asyncio
async def test_timeout_thrower():
    with rt.Session(logging_setting="NONE"):
        try:
            await rt.call(TimeoutThrower)
        except Exception as e:
            assert isinstance(e, asyncio.TimeoutError)


# ============================================ END Many calls and Timeout tests ============================================
