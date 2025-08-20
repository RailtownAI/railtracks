"""
Tests for the FunctionNode and from_function functionality.

This module tests the ability to create nodes from functions with various parameter types:
- Simple primitive types (int, str)
- Pydantic models
- Complex types (Tuple, List, Dict)
"""

import pytest
from typing import Tuple, List, Dict, Union, Optional
import railtracks as rt
from railtracks.llm import Message, AssistantMessage, Parameter
from railtracks.llm.response import Response

# ===== Test Classes =====
class TestPrimitiveInputTypes:
    def test_empty_function(self, _agent_node_factory, mock_llm):
        """Test that a function with no parameters works correctly."""

        def secret_phrase() -> str:
            """
            Function that returns a secret phrase.

            Returns:
                str: The secret phrase.
            """
            rt.context.put("secret_phrase_called", True)
            return "Constantinople"

        # ============ mock llm config =========
        async def invoke_child_tool(messages, tools):
            assert len(tools) == 1
            assert tools[0].name == "secret_phrase"

            tool_response = secret_phrase()

            return Response(
                message=AssistantMessage(
                    tool_response,
                ),
            )
        
        llm = mock_llm()
        llm._achat_with_tools = invoke_child_tool
        # =======================================

        agent = _agent_node_factory(
            secret_phrase,
            llm,
        )

        with rt.Session(logging_setting="NONE"):
            response = rt.call_sync(
                agent,
                "What is the secret phrase? Only return the secret phrase, no other text."
            )
            assert response.content == "Constantinople"
            assert rt.context.get("secret_phrase_called")

    def test_single_int_input(self, _agent_node_factory, mock_llm):
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

        # ============ mock llm config =========
        async def invoke_child_tool(messages, tools):
            assert len(tools) == 1
            assert tools[0].name == "magic_number"
            for parameter in tools[0].parameters:
                assert parameter.name == "input_num"
                assert parameter.param_type == "integer"
                assert parameter.description == "The input number to test."

            tool_response = magic_number(6)

            return Response(
                message=AssistantMessage(
                    tool_response,
                ),
            )
        
        llm = mock_llm()
        llm._achat_with_tools = invoke_child_tool
        # =======================================

        agent = _agent_node_factory(
            magic_number,
            llm,
        )

        with rt.Session(logging_setting="NONE") as run:
            response = rt.call_sync(
                agent,
                "Find what the magic function output is for 6? Only return the magic number, no other text."
            )
            assert rt.context.get("magic_number_called")
            assert response.content == "666666"


    def test_single_str_input(self, _agent_node_factory, mock_llm):
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

        # ============ mock llm config =========
        async def invoke_child_tool(messages, tools):
            assert len(tools) == 1
            assert tools[0].name == "magic_phrase"
            for parameter in tools[0].parameters:
                assert parameter.name == "word"
                assert parameter.param_type == "string"
                assert parameter.description == "The word to create the magic phrase from"

            tool_response = magic_phrase("hello")

            return Response(
                message=AssistantMessage(
                    tool_response,
                ),
            )
        
        llm = mock_llm()
        llm._achat_with_tools = invoke_child_tool
        # =======================================

        agent = _agent_node_factory(
            magic_phrase,
            llm,
        )

        with rt.Session(logging_setting="NONE") as run:
            response = rt.call_sync(
                agent,
                "What is the magic phrase for the word 'hello'? Only return the magic phrase, no other text."
            )
            assert rt.context.get("magic_phrase_called")
            assert response.content == "h$e$l$l$o"

    def test_single_float_input(self, _agent_node_factory, mock_llm):
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

        
        # ============ mock llm config =========
        async def invoke_child_tool(messages, tools):
            assert len(tools) == 1
            assert tools[0].name == "magic_test"
            for parameter in tools[0].parameters:
                assert parameter.name == "num"
                assert parameter.param_type == "number"
                assert parameter.description == "The number to test."

            tool_response = magic_test(5.0) 

            return Response(
                message=AssistantMessage(
                    tool_response,
                ),
            )
        
        llm = mock_llm()
        llm._achat_with_tools = invoke_child_tool
        # =======================================

        agent = _agent_node_factory(
            magic_test,
            llm,
        )

        with rt.Session(logging_setting="NONE") as run:
            response = rt.call_sync(
                agent,
                "Does 5 pass the magic test? Only return the result, no other text."
            )
            assert rt.context.get("magic_test_called")
            resp: str = response.content
            assert resp.lower() == "true"


    def test_single_bool_input(self, _agent_node_factory, mock_llm):
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

        # ============ mock llm config =========
        async def invoke_child_tool(messages, tools):
            assert len(tools) == 1
            assert tools[0].name == "magic_test"
            for parameter in tools[0].parameters:
                assert parameter.name == "is_magic"
                assert parameter.param_type == "boolean"
                assert parameter.description == "The boolean to test."

            tool_response = magic_test(True)

            return Response(
                message=AssistantMessage(
                    tool_response,
                ),
            )
        
        llm = mock_llm()
        llm._achat_with_tools = invoke_child_tool
        # =======================================

        agent = _agent_node_factory(
            magic_test,
            llm,
        )

        with rt.Session(logging_setting="NONE") as run:
            response = rt.call_sync(
                agent,
                "Is the magic test true? Only return the result, no other text."
            )
            assert rt.context.get("magic_test_called")
            assert response.content == "Wish Granted"

    # TODO: think carefully about how we can test the graceful error handling. This test is temporary.
    def test_function_error_handling(self, _agent_node_factory, mock_llm):
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

        # ============ mock llm config =========
        async def invoke_child_tool(messages, tools):
            assert len(tools) == 1
            assert tools[0].name == "error_function"
            for parameter in tools[0].parameters:
                assert parameter.name == "x"
                assert parameter.param_type == "integer"
                assert parameter.description == "The input number to the function"

            try:
                tool_response = error_function(0)
            except Exception as e:
                assert isinstance(e, ZeroDivisionError)
                return Response(
                    message=AssistantMessage(
                        "Division by zero error",
                    )
                )

        
        llm = mock_llm()
        llm._achat_with_tools = invoke_child_tool
        # =======================================

        agent = _agent_node_factory(
            error_function,
            llm,
        )

        with rt.Session(logging_setting="NONE"):
            output = rt.call_sync(
                agent,
                "What does the tool return for an input of 0? Only return the result, no other text."
            )

            assert output.content == "Division by zero error"
            assert rt.context.get("magic_test_called")


class TestSequenceInputTypes:
    def test_single_list_input(self, _agent_node_factory, mock_llm):
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


        # ============ mock llm config =========
        async def invoke_child_tool(messages, tools):
            assert len(tools) == 1
            assert tools[0].name == "magic_list"
            for parameter in tools[0].parameters:
                assert parameter.name == "items"
                assert parameter.param_type == "array"
                assert parameter.description == "The list of items to test."

            tool_response = magic_list(["1", "2", "3"])

            return Response(
                message=AssistantMessage(
                    tool_response,
                ),
            )

        
        llm = mock_llm()
        llm._achat_with_tools = invoke_child_tool
        # =======================================

        agent = _agent_node_factory(
            magic_list,
            llm,
        )

        with rt.Session(logging_setting="NONE") as run:
            response = rt.call_sync(
                agent,
                "What is the magic list for ['1', '2', '3']? Only return the result, no other text."
            )
            assert response.content == "3 2 1"
            assert rt.context.get("magic_list_called")


    def test_single_tuple_input(self, _agent_node_factory, mock_llm):
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

        agent = _agent_node_factory(
            magic_tuple,
            mock_llm(Message(content="3 2 1", role="assistant")),
        )

        with rt.Session(logging_setting="NONE") as run:
            response = rt.call_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "What is the magic tuple for ('1', '2', '3')? Only return the result, no other text."
                        )
                    ]
                ),
            )

            assert response.content == "3 2 1"
            assert rt.context.get("magic_tuple_called")


    def test_lists(self, _agent_node_factory, mock_llm):
        """Test that a function with a list parameter works correctly."""

        def magic_result(num_items: List[float], prices: List[float]) -> float:
            """
            Args:
                num_items (List[str]): The list of items to test.
                prices (List[float]): The list of prices to test.

            Returns:
                str: The result of the function.
            """
            rt.context.put("magic_result_called", True)
            total = sum(price * item for price, item in zip(prices, num_items))
            return total

        agent = _agent_node_factory(
            magic_result,
            mock_llm(Message(content="25.5", role="assistant")),
        )
        with rt.Session(logging_setting="NONE") as run:
            response = rt.call_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "What is the magic result for [1, 2] and [5.5, 10]? Only return the result, no other text."
                        )
                    ]
                ),
            )

        assert response.content == "25.5"


class TestDictionaryInputTypes:
    """Test that dictionary input types raise appropriate errors."""

    def test_dict_input_raises_error(self, _agent_node_factory, mock_llm):
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
                response = rt.call_sync(
                    agent,
                    rt.llm.MessageHistory(
                        [rt.llm.UserMessage("What is the result for {'key': 'value'}?")]
                    ),
                )

class TestUnionAndOptionalParameter:
    @pytest.mark.parametrize("type_annotation", [Union[int, str], int|str], ids=["union", "or notation union"])
    def test_union_parameter(self, type_annotation, _agent_node_factory, mock_llm):
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

        agent = _agent_node_factory(
            magic_number, mock_llm(Message(content="42", role="assistant"))
        )
        with rt.Session(logging_setting="QUIET") as run:
            response = rt.call_sync(
                agent,
                rt.llm.MessageHistory(
                    [rt.llm.UserMessage("Calculate the magic number for 5. Then calculate the magic number for 'fox'. Add them and return the result only.")]
                ),
            )
            assert rt.context.get("magic_number_called")
            assert response.content == "42"

    @pytest.mark.parametrize("deafult_value", [(None, 42), (5, 26)], ids=["default value", "non default value"])
    def test_optional_parameter(self, _agent_node_factory, deafult_value, mock_llm):
        """Test that a function with an optional parameter works correctly."""
        deafult, answer = deafult_value
        def magic_number(x: Optional[int] = deafult) -> int:
            """
            Args:
                x: The input parameter
                
            Returns:
                int: The result of the function
            """
            rt.context.put("magic_number_called", True)
            return 21 if x is None else x

        agent = _agent_node_factory(
            magic_number, mock_llm(Message(content=str(answer), role="assistant"))
        )
        with rt.Session(logging_setting="QUIET") as run:
            response = rt.call_sync(
                agent,
                rt.llm.MessageHistory(
                    [rt.llm.UserMessage("Calculate the magic number for 21. Then calculate the magic number with no args. Add them and return the result only.")]
                ),
            )

            assert response.content == str(answer)
            assert rt.context.get("magic_number_called")



        


