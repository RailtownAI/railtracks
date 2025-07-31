"""
Tests for the FunctionNode and from_function functionality.

This module tests the ability to create nodes from functions with various parameter types:
- Simple primitive types (int, str)
- Pydantic models
- Complex types (Tuple, List, Dict)
"""

import pytest
from typing import Tuple, List, Dict, Union, Optional
from pydantic import BaseModel, Field
import time


from railtracks.state.request import Failure
import railtracks as rt

# ===== Test Models =====

# Define model providers to test with
MODEL_PROVIDERS = ["openai"]


# ===== Test Classes =====
class TestPrimitiveInputTypes:
    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_empty_function(self, model_provider, create_top_level_node):
        """Test that a function with no parameters works correctly."""

        def secret_phrase() -> str:
            """
            Function that returns a secret phrase.

            Returns:
                str: The secret phrase.
            """
            return "Constantinople"

        agent = create_top_level_node(
            secret_phrase,
            model_provider=model_provider,
        )
        with rt.Session(logging_setting="NONE") as run:
            response = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "What is the secret phrase? Only return the secret phrase, no other text."
                        )
                    ]
                ),
            )
        assert response.answer.content == "Constantinople"

    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_single_int_input(self, model_provider, create_top_level_node):
        """Test that a function with a single int parameter works correctly."""

        def magic_number(input_num: int) -> str:
            """
            Args:
                input_num (int): The input number to test.

            Returns:
                str: The result of the function.
            """
            return str(input_num) * input_num

        agent = create_top_level_node(
            magic_number,
            model_provider=model_provider,
        )
        with rt.Session(logging_setting="NONE") as run:
            response = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "Find what the magic function output is for 6? Only return the magic number, no other text."
                        )
                    ]
                ),
            )

        assert response.answer.content == "666666"

    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_single_str_input(self, model_provider, create_top_level_node):
        """Test that a function with a single str parameter works correctly."""

        def magic_phrase(word: str) -> str:
            """
            Args:
                word (str): The word to create the magic phrase from

            Returns:
                str: The result of the function.
            """
            return "$".join(list(word))

        agent = create_top_level_node(
            magic_phrase,
            model_provider=model_provider,
        )
        with rt.Session(logging_setting="NONE") as run:
            response = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "What is the magic phrase for the word 'hello'? Only return the magic phrase, no other text."
                        )
                    ]
                ),
            )

        assert response.answer.content == "h$e$l$l$o"

    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_single_float_input(self, model_provider, create_top_level_node):
        """Test that a function with a single float parameter works correctly."""

        def magic_test(num: float) -> str:
            """
            Args:
                num (float): The number to test.

            Returns:
                str: The result of the function.
            """
            return str(isinstance(num, float))

        agent = create_top_level_node(
            magic_test,
            model_provider=model_provider,
        )
        with rt.Session(logging_setting="NONE") as run:
            response = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "Does 5 pass the magic test? Only return the result, no other text."
                        )
                    ]
                ),
            )

        assert response.answer.content == "True"

    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_single_bool_input(self, model_provider, create_top_level_node):
        """Test that a function with a single bool parameter works correctly."""

        def magic_test(is_magic: bool) -> str:
            """
            Args:
                is_magic (bool): The boolean to test.

            Returns:
                str: The result of the function.
            """
            return "Wish Granted" if is_magic else "Wish Denied"

        agent = create_top_level_node(
            magic_test,
            model_provider=model_provider,
        )
        with rt.Session(logging_setting="NONE") as run:
            response = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "Is the magic test true? Only return the result, no other text."
                        )
                    ]
                ),
            )
        assert response.answer.content == "Wish Granted"

    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_function_error_handling(self, model_provider, create_top_level_node):
        """Test that errors in function execution are handled gracefully."""

        def error_function(x: int) -> str:
            """
            Args:
                x (int): The input number to the function

            Returns:
                str: The result of the function.
            """
            return str(1 / x)

        agent = create_top_level_node(
            error_function,
            model_provider=model_provider,
        )
        with rt.Session(logging_setting="NONE") as run:
            output = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "What does the tool return for an input of 0? Only return the result, no other text."
                        )
                    ]
                ),
            )

            i_r = output.request_forest.insertion_request[0]
            children = output.request_forest.children(i_r.sink_id)[0]

            assert isinstance(children.output, Failure)


class TestSequenceInputTypes:
    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_single_list_input(self, model_provider, create_top_level_node):
        """Test that a function with a single list parameter works correctly."""

        def magic_list(items: List[str]) -> str:
            """
            Args:
                items (List[str]): The list of items to test.

            Returns:
                str: The result of the function.
            """
            items_copy = items.copy()
            items_copy.reverse()
            return " ".join(items_copy)

        agent = create_top_level_node(
            magic_list,
            model_provider=model_provider,
        )
        with rt.Session(logging_setting="NONE") as run:
            response = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "What is the magic list for ['1', '2', '3']? Only return the result, no other text."
                        )
                    ]
                ),
            )
        assert response.answer.content == "3 2 1"

    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_single_tuple_input(self, model_provider, create_top_level_node):
        """Test that a function with a single tuple parameter works correctly."""

        def magic_tuple(items: Tuple[str, str, str]) -> str:
            """
            Args:
                items (Tuple[str, str, str]): The tuple of items to test.

            Returns:
                str: The result of the function.
            """
            return " ".join(reversed(items))

        agent = create_top_level_node(
            magic_tuple,
            model_provider=model_provider,
        )

        with rt.Session(logging_setting="NONE") as run:
            response = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "What is the magic tuple for ('1', '2', '3')? Only return the result, no other text."
                        )
                    ]
                ),
            )

        assert response.answer.content == "3 2 1"

    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_lists(self, model_provider, create_top_level_node):
        """Test that a function with a list parameter works correctly."""

        def magic_result(num_items: List[float], prices: List[float]) -> float:
            """
            Args:
                num_items (List[str]): The list of items to test.
                prices (List[float]): The list of prices to test.

            Returns:
                str: The result of the function.
            """
            total = sum(price * item for price, item in zip(prices, num_items))
            return total

        agent = create_top_level_node(
            magic_result,
            model_provider=model_provider,
        )
        with rt.Session(logging_setting="NONE") as run:
            response = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [
                        rt.llm.UserMessage(
                            "What is the magic result for [1, 2] and [5.5, 10]? Only return the result, no other text."
                        )
                    ]
                ),
            )

        assert response.answer.content == "25.5"


class TestDictionaryInputTypes:
    """Test that dictionary input types raise appropriate errors."""

    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_dict_input_raises_error(self, model_provider, create_top_level_node):
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
            agent = create_top_level_node(dict_func, model_provider=model_provider)
            with rt.Session(logging_setting="NONE") as run:
                response = run.run_sync(
                    agent,
                    rt.llm.MessageHistory(
                        [rt.llm.UserMessage("What is the result for {'key': 'value'}?")]
                    ),
                )

class TestUnionAndOptionalParameter:
    @pytest.mark.parametrize("type_annotation", [Union[int, str], int|str], ids=["union", "or notation union"])
    def test_union_parameter(self, type_annotation, create_top_level_node):
        """Test that a function with a union parameter works correctly."""
        def magic_number(x: type_annotation) -> int:
            """
            Args:
                x: The input parameter
                
            Returns:
                int: The result of the function
            """
            return 21

        agent = create_top_level_node(
            magic_number, model_provider="openai"
        )
        with rt.Session(logging_setting="QUIET") as run:
            response = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [rt.llm.UserMessage("Calculate the magic number for 5. Then calculate the magic number for 'fox'. Add them and return the result only.")]
                ),
            )

        assert response.answer.content == "42"

    @pytest.mark.parametrize("deafult_value", [(None, 42), (5, 26)], ids=["default value", "non default value"])
    def test_optional_parameter(self, create_top_level_node, deafult_value):
        """Test that a function with an optional parameter works correctly."""
        deafult, answer = deafult_value
        def magic_number(x: Optional[int] = deafult) -> int:
            """
            Args:
                x: The input parameter
                
            Returns:
                int: The result of the function
            """
            return 21 if x is None else x

        agent = create_top_level_node(
            magic_number, model_provider="openai"
        )
        with rt.Session(logging_setting="QUIET") as run:
            response = run.run_sync(
                agent,
                rt.llm.MessageHistory(
                    [rt.llm.UserMessage("Calculate the magic number for 21. Then calculate the magic number with no args. Add them and return the result only.")]
                ),
            )

        assert response.answer.content == str(answer)


class TestRealisticScenarios:
    @pytest.mark.parametrize("model_provider", MODEL_PROVIDERS)
    def test_realistic_scenario(self, model_provider, create_top_level_node):
        """Test that a function with a realistic scenario works correctly."""

        class StaffDirectory(BaseModel):
            name: str = Field(description="The name of the staff member")
            role: str = Field(description="The role of the staff member")
            phone: str = Field(description="The phone number of the staff member")

        # Define DB at class level so it's accessible for assertions
        DB = {
            "John": {"role": "Manager", "phone": "1234567890"},
        }

        def update_staff_directory(staff: List[StaffDirectory]) -> None:
            """
            For a given list of staff, updates the staff directory with new members or updates existing members.

            Args:
                staff (List[StaffDirectory]): The list of staff to to gather information about.

            """
            for person in staff:
                DB[person.name] = {"role": person.role, "phone": person.phone}

        usr_prompt = (
            "Update the staff directory with the following information: John is now a 'Senior Manager' and his phone number is changed to 5555"
            " and Jane is new a Developer and her phone number is 0987654321."
        )

        agent = create_top_level_node(
            update_staff_directory, model_provider=model_provider
        )

        with rt.Session(logging_setting="NONE") as run:
            response = run.run_sync(
                agent, rt.llm.MessageHistory([rt.llm.UserMessage(usr_prompt)])
            )
            print(response)

        assert DB["John"]["role"] == "Senior Manager"
        assert DB["John"]["phone"] == "5555"
        assert DB["Jane"]["role"] == "Developer"
        assert DB["Jane"]["phone"] == "0987654321"
        


