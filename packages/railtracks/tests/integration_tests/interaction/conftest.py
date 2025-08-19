import asyncio

import pytest
from typing import List, Literal, Type
import copy
from pydantic import BaseModel, Field
import railtracks as rt
from railtracks.llm.response import Response, MessageInfo


# ====================================== Mock Model ======================================

@pytest.fixture
def mock_model():
    """
    Fixture to mock OpenAILLM methods with configurable responses.
    Pass a custom_response_message to override the message in all default responses.
    Usage:
        model = mock_model(custom_response_message=rt.llm.Message(content="custom", role="assistant"))
    """
    class MockOpenAILLM(rt.llm.OpenAILLM):
        def __init__(self, custom_response_message: rt.llm.Message | None = None):
            super().__init__("gpt-4o")
            self.custom_response_message = custom_response_message
            self.mocked_message_info = MessageInfo(
                input_tokens=42,
                output_tokens=42,
                latency=1.42,
                model_name="mock_model",
                total_cost=0.00042,
                system_fingerprint="fp_4242424242",
            )

        def get_message(self, default_content: str | BaseModel, role: Literal["assistant", "user", "system", "tool"] = "assistant") -> rt.llm.Message:
            return self.custom_response_message or rt.llm.Message(content=default_content, role=role)

        # Override all methods that make network calls with mocks
        async def _achat(self, messages, **kwargs):
            return Response(
                message=self.get_message("mocked Message"),
                streamer=None,
                message_info=self.mocked_message_info,
            )

        async def _astructured(self, messages, schema, **kwargs):
            class DummyStructured(BaseModel):
                dummy_attr: str = "mocked"
            return Response(
                message=self.get_message(DummyStructured()),
                streamer=None,
                message_info=self.mocked_message_info
            )

        async def _achat_with_tools(self, messages, tools, **kwargs):
            return Response(
                message=self.get_message("mocked tool message"),
                streamer=None,
                message_info=self.mocked_message_info,
            )

    return MockOpenAILLM
# ====================================== End Mock Model ======================================


# ====================================== System Messages ======================================
@pytest.fixture
def terminal_llms_system_messages():
    system_rng = "You are a random integer generator that will return a random list of integers between 0 and 100. Do not return more than 10 integers."
    system_rng_operation = "You are a random mathematical operation calculator that will apply a random operation to the list of integers that will be provided by the user and return the result. The answer should be only a single integer."
    system_math_genius = "You are a math genius that will get a list of integers(loi) and another interger(x), your task is to predict what operation must be appled to the list of integers to get the result of x."

    return system_rng, system_rng_operation, system_math_genius


@pytest.fixture
def structured_llms_system_messages():
    system_undergrad_student = "You are an undergraduate university student. You are taking a math class where you need to write proofs. Be concise and to the point."
    system_professor = "You are a senior Math professor at a university. You need to grade the students work (scale of 0 to 100) and give a reasoning for the grading."

    return system_undergrad_student, system_professor


@pytest.fixture
def tool_call_llm_system_messages():
    system_currency_converter = "You are a currency converter that will convert currencies. you have access to AvailabelCurrencies and ConvertCurrency tools. Use them when you need to."
    system_travel_planner = "You are a travel planner that will plan a trip. you have access to AvailableLocations, CurrencyUsed and AverageLocationCost tools. Use them when you need to."
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
def terminal_nodes(mock_model, terminal_llms_system_messages):
    """
    Returns the appropriate nodes based on the parametrized fixture name.
    """
    system_rng, system_rng_operation, system_math_genius = terminal_llms_system_messages
    rng_node = rt.agent_node(
        name="RNG Node", system_message=system_rng, llm_model=mock_model()
    )
    rng_operation_node = rt.agent_node(
        name="RNG Operation Node",
        system_message=system_rng_operation,
        llm_model=mock_model(),
    )
    math_detective_node = rt.agent_node(
        name="Math Detective Node",
        system_message=system_math_genius,
        llm_model=mock_model(),
    )

    return rng_node, rng_operation_node, math_detective_node


@pytest.fixture
def structured_nodes(mock_model, structured_llms_system_messages):
    """
    Returns the appropriate nodes based on the parametrized fixture name.
    """
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

    # Mock responses
    math_undergrad_response = rt.llm.Message(content=ProofModel(proof="Mocked proof"), role="assistant")
    math_professor_response = rt.llm.Message(content=GradingSchema(overall_score=100, feedback="Mocked feedback"), role="assistant")

    math_undergrad_student_node = rt.agent_node(
        name="Math Undergraduate Student Node",
        output_schema=ProofModel,
        system_message=system_undergrad_student,
        llm_model=mock_model(math_undergrad_response),
    )
    math_professor_node = rt.agent_node(
        name="Math Professor Node",
        output_schema=GradingSchema,
        system_message=system_professor,
        llm_model=mock_model(math_professor_response),
    )

    return math_undergrad_student_node, math_professor_node


@pytest.fixture
def tool_calling_nodes(
    mock_model,
    tool_call_llm_system_messages,
    currency_converter_tools,
    travel_planner_tools,
):
    """
    Returns the appropriate nodes based on the parametrized fixture name.
    """
    available_currencies, convert_currency = currency_converter_tools
    available_locations, currency_used, average_location_cost = travel_planner_tools
    system_currency_converter, system_travel_planner = tool_call_llm_system_messages

    AvailableCurrencies = rt.function_node(available_currencies)
    ConvertCurrency = rt.function_node(convert_currency)
    AvailableLocations = rt.function_node(available_locations)
    CurrencyUsed = rt.function_node(currency_used)
    AverageLocationCost = rt.function_node(average_location_cost)

    currency_converter_node = rt.agent_node(
        tool_nodes={AvailableCurrencies, ConvertCurrency},
        name="Currency Converter Node",
        system_message=system_currency_converter,
        llm_model=mock_model(),
    )
    travel_planner_node = rt.agent_node(
        tool_nodes={AvailableLocations, CurrencyUsed, AverageLocationCost},
        name="Travel Planner Node",
        system_message=system_travel_planner,
        llm_model=mock_model(),
    )

    return currency_converter_node, travel_planner_node


@pytest.fixture
def parallel_node():
    """
    A simple node that runs a function in parallel a specified number of times.
    """

    async def sleep(timeout_len: float) -> float:
        """A simple function that sleeps for a given time."""
        await asyncio.sleep(timeout_len)
        return timeout_len

    TimeoutNode = rt.function_node(sleep)

    async def parallel_function(timeout_config: List[float]):
        return await rt.call_batch(TimeoutNode, timeout_config)

    return rt.function_node(parallel_function)


# ====================================== End Nodes ======================================
