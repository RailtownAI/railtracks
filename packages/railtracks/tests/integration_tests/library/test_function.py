"""
Tests for the FunctionNode and from_function functionality.

This module tests the ability to create nodes from functions with various parameter types:
- Simple primitive types (int, str)
- Pydantic models
- Complex types (Tuple, List, Dict)
"""

import re
from typing import Dict, List, Optional, Tuple, Union

import pytest
import railtracks as rt
from railtracks.llm import ToolCall


# ===== Test Classes =====
class TestPrimitiveInputTypes:
    async def test_empty_function(self, _agent_node_factory, mock_llm):
        """Test that a function with no parameters works correctly."""

        def secret_phrase() -> str:
            """
            Function that returns a secret phrase.

            Returns:
                str: The secret phrase.
            """
            rt.context.put("secret_phrase_called", True)
            return "Constantinople"

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(name="secret_phrase", identifier="id_42424242", arguments={})
            ]
        )

        agent = _agent_node_factory(
            secret_phrase,
            llm,
        )

        with rt.Session(logging_setting="NONE"):
            response = await rt.call(
                agent,
                "What is the secret phrase? Only return the secret phrase, no other text.",
            )
            assert "Constantinople" in response.content
            assert rt.context.get("secret_phrase_called")

    async def test_single_int_input(self, _agent_node_factory, mock_llm):
        """Test that a function with a single int parameter works correctly."""

        def magic_number(input_num: int) -> str:
            """
            Args:
                input_num (int): The input number to test.

            Returns:
                str: The result of the function.
            """
            rt.context.put("magic_number_called", True)
            return str(input_num) * input_num

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="magic_number",
                    identifier="id_42424242",
                    arguments={"input_num": 6},
                )
            ]
        )
        # =======================================

        agent = _agent_node_factory(
            magic_number,
            llm,
        )

        with rt.Session(logging_setting="NONE"):
            response = await rt.call(
                agent,
                "Find what the magic function output is for 6? Only return the magic number, no other text.",
            )
            assert rt.context.get("magic_number_called")
            assert "666666" in response.content

    async def test_single_str_input(self, _agent_node_factory, mock_llm):
        """Test that a function with a single str parameter works correctly."""

        def magic_phrase(word: str) -> str:
            """
            Args:
                word (str): The word to create the magic phrase from

            Returns:
                str: The result of the function.
            """
            rt.context.put("magic_phrase_called", True)
            return "$".join(list(word))

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="magic_phrase",
                    identifier="id_42424242",
                    arguments={"word": "hello"},
                )
            ]
        )
        # =======================================

        agent = _agent_node_factory(
            magic_phrase,
            llm,
        )

        with rt.Session(logging_setting="NONE"):
            response = await rt.call(
                agent,
                "What is the magic phrase for the word 'hello'? Only return the magic phrase, no other text.",
            )
            assert rt.context.get("magic_phrase_called")
            assert "h$e$l$l$o" in response.content

    async def test_single_float_input(self, _agent_node_factory, mock_llm):
        """Test that a function with a single float parameter works correctly."""

        def magic_test(num: float) -> str:
            """
            Args:
                num (float): The number to test.

            Returns:
                str: The result of the function.
            """
            rt.context.put("magic_test_called", True)
            return str(isinstance(num, float))

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="magic_test",
                    identifier="id_42424242",
                    arguments={"num": 5.0},
                )
            ]
        )
        # =======================================

        agent = _agent_node_factory(
            magic_test,
            llm,
        )

        with rt.Session(logging_setting="NONE"):
            response = await rt.call(
                agent,
                "Does 5 pass the magic test? Only return the result, no other text.",
            )
            assert rt.context.get("magic_test_called")
            resp: str = response.content
            assert "True" in resp

    async def test_single_bool_input(self, _agent_node_factory, mock_llm):
        """Test that a function with a single bool parameter works correctly."""

        def magic_test(is_magic: bool) -> str:
            """
            Args:
                is_magic (bool): The boolean to test.

            Returns:
                str: The result of the function.
            """
            rt.context.put("magic_test_called", True)
            return "Wish Granted" if is_magic else "Wish Denied"

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="magic_test",
                    identifier="id_42424242",
                    arguments={"is_magic": True},
                )
            ]
        )
        # =======================================

        agent = _agent_node_factory(
            magic_test,
            llm,
        )

        with rt.Session(logging_setting="NONE"):
            response = await rt.call(
                agent, "Is the magic test true? Only return the result, no other text."
            )
            assert rt.context.get("magic_test_called")
            assert "Wish Granted" in response.content

    # TODO: think carefully about how we can test the graceful error handling. This test is temporary.
    async def test_function_error_handling(self, _agent_node_factory, mock_llm):
        """Test that errors in function execution are handled gracefully."""

        def error_function(x: int) -> str:
            """
            Args:
                x (int): The input number to the function

            Returns:
                str: The result of the function.
            """
            rt.context.put("magic_test_called", True)
            return str(1 / x)

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="error_function",
                    identifier="id_42424242",
                    arguments={"x": 0},
                )
            ]
        )
        # =======================================

        agent = _agent_node_factory(
            error_function,
            llm,
        )

        with rt.Session(logging_setting="NONE"):
            output = await rt.call(
                agent,
                "What does the tool return for an input of 0? Only return the result, no other text.",
            )

            assert (
                "There was an error running the tool" in output.content
            )  # graceful error handling
            assert rt.context.get("magic_test_called")


class TestSequenceInputTypes:
    async def test_single_list_input(self, _agent_node_factory, mock_llm):
        """Test that a function with a single list parameter works correctly."""

        def magic_list(items: List[str]) -> str:
            """
            Args:
                items (List[str]): The list of items to test.

            Returns:
                str: The result of the function.
            """
            rt.context.put("magic_list_called", True)
            items_copy = items.copy()
            items_copy.reverse()
            return " ".join(items_copy)

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="magic_list",
                    identifier="id_42424242",
                    arguments={"items": ["1", "2", "3"]},
                )
            ]
        )
        # =======================================

        agent = _agent_node_factory(
            magic_list,
            llm,
        )

        with rt.Session(logging_setting="NONE"):
            response = await rt.call(
                agent,
                "What is the magic list for ['1', '2', '3']? Only return the result, no other text.",
            )
            assert "3 2 1" in response.content
            assert rt.context.get("magic_list_called")

    async def test_single_tuple_input(self, _agent_node_factory, mock_llm):
        """Test that a function with a single tuple parameter works correctly."""

        def magic_tuple(items: Tuple[str, str, str]) -> str:
            """
            Args:
                items (Tuple[str, str, str]): The tuple of items to test.

            Returns:
                str: The result of the function.
            """
            rt.context.put("magic_tuple_called", True)
            return " ".join(reversed(items))

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="magic_tuple",
                    identifier="id_42424242",
                    arguments={"items": ("1", "2", "3")},
                )
            ]
        )
        # =======================================

        agent = _agent_node_factory(
            magic_tuple,
            llm,
        )
        with rt.Session(logging_setting="NONE"):
            response = await rt.call(
                agent,
                "What is the magic tuple for ('1', '2', '3')? Only return the result, no other text.",
            )

            assert "3 2 1" in response.content
            assert rt.context.get("magic_tuple_called")

    async def test_lists(self, _agent_node_factory, mock_llm):
        """Test that a function with a list parameter works correctly."""

        def magic_result(num_items: List[float], prices: List[float]) -> float:
            """
            Args:
                num_items (List[float]): The list of items to test.
                prices (List[float]): The list of prices to test.

            Returns:
                str: The result of the function.
            """
            rt.context.put("magic_result_called", True)
            total = sum(price * item for price, item in zip(prices, num_items))
            return total

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="magic_result",
                    identifier="id_42424242",
                    arguments={"num_items": [1.0, 2.0], "prices": [5.5, 10.0]},
                )
            ]
        )
        # =======================================

        agent = _agent_node_factory(
            magic_result,
            llm,
        )
        with rt.Session(logging_setting="NONE"):
            response = await rt.call(
                agent,
                "What is the magic result for [1, 2] and [5.5, 10]? Only return the result, no other text.",
            )

        assert "25.5" in response.content


class TestDictionaryInputTypes:
    """Test that dictionary input types raise appropriate errors."""

    async def test_dict_input_raises_error(self, _agent_node_factory, mock_llm):
        """Test that a function with a dictionary parameter raises an error."""

        def dict_func(data: Dict[str, str]):
            """
            Args:
                data (Dict[str, str]): A dictionary input that should raise an error

            Returns:
                str: This should never be reached
            """
            return "test"

        with pytest.raises(Exception):
            agent = _agent_node_factory(dict_func, mock_llm())
            with rt.Session(logging_setting="NONE"):
                await rt.call(
                    agent,
                    rt.llm.MessageHistory(
                        [rt.llm.UserMessage("What is the result for {'key': 'value'}?")]
                    ),
                )


class TestUnionAndOptionalParameter:
    @pytest.mark.parametrize(
        "type_annotation",
        [Union[int, str], int | str],
        ids=["union", "or notation union"],
    )
    async def test_union_parameter(
        self, type_annotation, _agent_node_factory, mock_llm
    ):
        """Test that a function with a union parameter works correctly."""

        def magic_number(x: type_annotation) -> int:
            """
            Args:
                x: The input parameter

            Returns:
                int: The result of the function
            """
            rt.context.put("magic_number_called", True)
            return 21

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="magic_number",
                    identifier="id_42424242",
                    arguments={"x": 5},
                ),
                ToolCall(
                    name="magic_number",
                    identifier="id_42424242",
                    arguments={"x": "fox"},
                ),
            ]
        )
        # =======================================

        agent = _agent_node_factory(
            magic_number,
            llm,
        )

        with rt.Session(logging_setting="CRITICAL"):
            response = await rt.call(
                agent,
                "Calculate the magic number for 5. Then calculate the magic number for 'fox'.",
            )
            assert rt.context.get("magic_number_called")
            assert len(re.findall(r"21", response.content)) == 2  # 21 appears twice

    @pytest.mark.parametrize(
        "default_value, expected",
        [
            (None, [21, 21]),  # default: both calls return 21
            (5, [21, 5]),  # non-default: first call 21, second call default (5)
        ],
        ids=["default value", "non default value"],
    )
    async def test_optional_parameter(
        self, _agent_node_factory, default_value, expected, mock_llm
    ):
        """Test that a function with an optional parameter works correctly."""

        def magic_number(x: Optional[int] = default_value) -> int:
            """
            Args:
                x: The input parameter

            Returns:
                int: The result of the function
            """
            rt.context.put("magic_number_called", True)
            return 21 if x is None else x

        # mock_llm will run the tool and return the result if requested
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(
                    name="magic_number",
                    identifier="id_42424242",
                    arguments={"x": 21},
                ),
                ToolCall(name="magic_number", identifier="id_42424242", arguments={}),
            ]
        )

        agent = _agent_node_factory(magic_number, llm)

        with rt.Session(logging_setting="CRITICAL"):
            response = await rt.call(
                agent,
                "Calculate the magic number for 21. Then calculate the magic number with no args.",
            )

            # verify each expected number appears in the response
            for val in expected:
                assert str(val) in response.content

            # also check counts if you want stricter validation
            for val in set(expected):
                assert len(re.findall(str(val), response.content)) == expected.count(
                    val
                )

            assert rt.context.get("magic_number_called")
