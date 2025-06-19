import random
import asyncio

import pytest
from typing import List
from pydantic import BaseModel, Field
import requestcompletion as rc


@pytest.fixture
def model():
    return rc.llm.OpenAILLM("gpt-4o")


# ====================================== System Messages ======================================
@pytest.fixture
def terminal_llms_system_messages():
    system_rng = rc.llm.SystemMessage(
        "You are a random integer generator that will return a random list of integers between 0 and 100. Do not return more than 10 integers."
    )
    system_rng_operation = rc.llm.SystemMessage(
        "You are a random mathematical operation calculator that will apply a random operation to the list of integers that will be provided by the user and return the result. The answer should be only a single integer."
    )
    system_math_genius = rc.llm.SystemMessage(
        "You are a math genius that will get a list of integers(loi) and another interger(x), your task is to predict what operation must be appled to the list of integers to get the result of x."
    )

    return system_rng, system_rng_operation, system_math_genius


@pytest.fixture
def structured_llms_system_messages():
    system_undergrad_student = rc.llm.SystemMessage(
        "You are an undergraduate university student. You are taking a math class where you need to write proofs. Be concise and to the point."
    )
    system_professor = rc.llm.SystemMessage(
        "You are a senior Math professor at a university. You need to grade the students work (scale of 0 to 100) and give a reasoning for the grading."
    )

    return system_undergrad_student, system_professor


@pytest.fixture
def tool_call_llm_system_messages():
    system_currency_converter = rc.llm.SystemMessage(
        "You are a currency converter that will convert currencies. you have access to AvailabelCurrencies and ConvertCurrency tools. Use them when you need to."
    )
    system_travel_planner = rc.llm.SystemMessage(
        "You are a travel planner that will plan a trip. you have access to AvailableLocations, CurrencyUsed and AverageLocationCost tools. Use them when you need to."
    )
    return system_currency_converter, system_travel_planner


# ====================================== End System Messages ======================================


# ====================================== Tools ======================================
@pytest.fixture
def currency_converter_tools():
    def available_currencies() -> List[str]:
        """Returns a list of available currencies.
        Args:
        Returns:
            List[str]: A list of available currencies.
        """
        return ["USD", "EUR", "INR"]

    def convert_currency(amount: float, from_currency: str, to_currency: str) -> float:
        """Converts currency using a static exchange rate (for testing purposes).
        Args:
            amount (float): The amount to convert.
            from_currency (str): The currency to convert from.
            to_currency (str): The currency to convert to.
        Returns:
            float: The converted amount.
        Raises:
            ValueError: If the exchange rate is not available.
        """
        exchange_rates = {
            ("USD", "EUR"): 0.85,
            ("EUR", "USD"): 1.1765,
            ("USD", "INR"): 83.0,
            ("INR", "USD"): 0.01205,
            ("EUR", "INR"): 98.0,
            ("INR", "EUR"): 0.0102,
        }

        rate = exchange_rates.get((from_currency, to_currency))
        if rate is None:
            raise ValueError("Exchange rate not available")
        return amount * rate

    return available_currencies, convert_currency


@pytest.fixture
def travel_planner_tools():
    def available_locations() -> List[str]:
        """Returns a list of available locations.
        Args:
        Returns:
            List[str]: A list of available locations.
        """
        return [
            "New York",
            "Los Angeles",
            "Chicago",
            "Delhi",
            "Mumbai",
            "Bangalore",
            "Paris",
            "Denmark",
            "Sweden",
            "Norway",
            "Germany",
        ]

    def currency_used(location: str) -> str:
        """Returns the currency used in a location.
        Args:
            location (str): The location to get the currency used for.
        Returns:
            str: The currency used in the location.
        """
        currency_map = {
            "New York": "USD",
            "Los Angeles": "USD",
            "Chicago": "USD",
            "Delhi": "INR",
            "Mumbai": "INR",
            "Bangalore": "INR",
            "Paris": "EUR",
            "Denmark": "EUR",
            "Sweden": "EUR",
            "Norway": "EUR",
            "Germany": "EUR",
        }
        used_currency = currency_map.get(location)
        if used_currency is None:
            raise ValueError(f"Currency not available for location: {location}")
        return used_currency

    def average_location_cost(location: str, num_days: int) -> float:
        """Returns the average cost of living in a location for a given number of days.
        Args:
            location (str): The location to get the cost of living for.
            num_days (int): The number of days for the trip.
        Returns:
            float: The average cost of living in the location.
        """
        daily_costs = {
            "New York": 200.0,
            "Los Angeles": 180.0,
            "Chicago": 150.0,
            "Delhi": 50.0,
            "Mumbai": 55.0,
            "Bangalore": 60.0,
            "Paris": 220.0,
            "Denmark": 250.0,
            "Sweden": 240.0,
            "Norway": 230.0,
            "Germany": 210.0,
        }
        daily_cost = daily_costs.get(location)
        if daily_cost is None:
            raise ValueError(f"Cost information not available for location: {location}")
        return daily_cost * num_days

    return available_locations, currency_used, average_location_cost


# ====================================== End Tools ======================================


# ====================================== Nodes ======================================
@pytest.fixture
def terminal_nodes(request, model, terminal_llms_system_messages):
    """
    Returns the appropriate nodes based on the parametrized fixture name.
    """
    fixture_name = request.param
    system_rng, system_rng_operation, system_math_genius = terminal_llms_system_messages

    if fixture_name == "easy_wrapper":
        rng_node = rc.library.terminal_llm(
            pretty_name="RNG Node", system_message=system_rng, model=model
        )
        rng_operation_node = rc.library.terminal_llm(
            pretty_name="RNG Operation Node",
            system_message=system_rng_operation,
            model=model,
        )
        math_detective_node = rc.library.terminal_llm(
            pretty_name="Math Detective Node",
            system_message=system_math_genius,
            model=model,
        )

        return rng_node, rng_operation_node, math_detective_node

    elif fixture_name == "class_based":

        def make_terminal_llm_class_version(
            pretty_name: str, system_message: rc.llm.SystemMessage
        ):
            class TerminalLLMNode(rc.library.TerminalLLM):
                def __init__(
                    self,
                    message_history: rc.llm.MessageHistory,
                    llm_model: rc.llm.ModelBase,
                ):
                    message_history = [x for x in message_history if x.role != "system"]
                    message_history.insert(0, system_message)
                    super().__init__(message_history=message_history, model=llm_model)

                @classmethod
                def pretty_name(cls) -> str:
                    return pretty_name

            return TerminalLLMNode

        rng_node = make_terminal_llm_class_version(
            "RNG Node", system_message=system_rng
        )
        rng_operation_node = make_terminal_llm_class_version(
            "RNG Operation Node", system_message=system_rng_operation
        )
        math_detective_node = make_terminal_llm_class_version(
            "Math Detective Node", system_message=system_math_genius
        )

        return rng_node, rng_operation_node, math_detective_node

    else:
        raise ValueError(f"Unknown node fixture: {fixture_name}")


@pytest.fixture
def structured_nodes(request, model, structured_llms_system_messages):
    """
    Returns the appropriate nodes based on the parametrized fixture name.
    """
    fixture_name = request.param
    system_undergrad_student, system_professor = structured_llms_system_messages

    class ProofModel(BaseModel):
        proof: str = Field(description="The mathematical proof of the statement")

    class GradingSchema(BaseModel):
        overall_score: float = Field(
            description="The grade on the proof on a scale of 0 to 100"
        )
        feedback: str = Field(
            description="Any suggestions on improving the proof or reason for the grade"
        )

    if fixture_name == "easy_wrapper":
        math_undergrad_student_node = rc.library.structured_llm(
            pretty_name="Math Undergraduate Student Node",
            output_model=ProofModel,
            system_message=system_undergrad_student,
            model=model,
        )
        math_professor_node = rc.library.structured_llm(
            pretty_name="Math Professor Node",
            output_model=GradingSchema,
            system_message=system_professor,
            model=model,
        )

        return math_undergrad_student_node, math_professor_node

    elif fixture_name == "class_based":

        def make_structured_llm_class_version(
            pretty_name: str,
            system_message: rc.llm.SystemMessage,
            output_model: BaseModel,
        ):
            class StructuredLLMNode(rc.library.StructuredLLM):
                def __init__(
                    self,
                    message_history: rc.llm.MessageHistory,
                    llm_model: rc.llm.ModelBase,
                ):
                    message_history = [x for x in message_history if x.role != "system"]
                    message_history.insert(0, system_message)
                    super().__init__(message_history=message_history, model=llm_model)

                @classmethod
                def output_model(cls) -> BaseModel:
                    return output_model

                @classmethod
                def pretty_name(cls) -> str:
                    return pretty_name

            return StructuredLLMNode

        math_undergrad_student_node = make_structured_llm_class_version(
            "Math Undergraduate Student Node",
            output_model=ProofModel,
            system_message=system_undergrad_student,
        )
        math_professor_node = make_structured_llm_class_version(
            "Math Professor Node",
            output_model=GradingSchema,
            system_message=system_professor,
        )

        return math_undergrad_student_node, math_professor_node

    else:
        raise ValueError(f"Unknown node fixture: {fixture_name}")


@pytest.fixture
def tool_calling_nodes(
    request,
    model,
    tool_call_llm_system_messages,
    currency_converter_tools,
    travel_planner_tools,
):
    """
    Returns the appropriate nodes based on the parametrized fixture name.
    """
    fixture_name = request.param
    available_currencies, convert_currency = currency_converter_tools
    available_locations, currency_used, average_location_cost = travel_planner_tools
    system_currency_converter, system_travel_planner = tool_call_llm_system_messages

    AvailableCurrencies = rc.library.from_function(available_currencies)
    ConvertCurrency = rc.library.from_function(convert_currency)
    AvailableLocations = rc.library.from_function(available_locations)
    CurrencyUsed = rc.library.from_function(currency_used)
    AverageLocationCost = rc.library.from_function(average_location_cost)

    if fixture_name == "easy_wrapper":
        currency_converter_node = rc.library.tool_call_llm(
            connected_nodes={AvailableCurrencies, ConvertCurrency},
            pretty_name="Currency Converter Node",
            system_message=system_currency_converter,
            model=model,
        )
        travel_planner_node = rc.library.tool_call_llm(
            connected_nodes={AvailableLocations, CurrencyUsed, AverageLocationCost},
            pretty_name="Travel Planner Node",
            system_message=system_travel_planner,
            model=model,
        )

        return currency_converter_node, travel_planner_node
    elif fixture_name == "class_based":

        def make_tool_call_llm_class_version(
            pretty_name: str,
            system_message: rc.llm.SystemMessage,
            connected_nodes: List[rc.Node],
        ):
            class ToolCallLLMNode(rc.library.ToolCallLLM):
                def __init__(
                    self,
                    message_history: rc.llm.MessageHistory,
                    llm_model: rc.llm.ModelBase,
                ):
                    message_history = [x for x in message_history if x.role != "system"]
                    message_history.insert(0, system_message)
                    super().__init__(message_history=message_history, model=llm_model)

                def connected_nodes(self):
                    return connected_nodes

                @classmethod
                def pretty_name(cls) -> str:
                    return pretty_name

            return ToolCallLLMNode

        currency_converter_node = make_tool_call_llm_class_version(
            "Currency Converter Node",
            system_message=system_currency_converter,
            connected_nodes=[AvailableCurrencies, ConvertCurrency],
        )
        travel_planner_node = make_tool_call_llm_class_version(
            "Travel Planner Node",
            system_message=system_travel_planner,
            connected_nodes=[AvailableLocations, CurrencyUsed, AverageLocationCost],
        )

        return currency_converter_node, travel_planner_node

    else:
        raise ValueError(f"Unknown node fixture: {fixture_name}")


@pytest.fixture
def parallel_node():
    """
    A simple node that runs a function in parallel a specified number of times.
    """

    async def sleep(timeout_len: float) -> float:
        """A simple function that sleeps for a given time."""
        await asyncio.sleep(timeout_len)
        return timeout_len

    TimeoutNode = rc.library.from_function(sleep)

    async def parallel_function(timeout_config: List[float]):
        return await rc.batch(TimeoutNode, timeout_config)

    return rc.library.from_function(parallel_function)


# ====================================== End Nodes ======================================
