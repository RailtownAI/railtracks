import pytest
import requestcompletion as rc
from typing import List
from pydantic import BaseModel, Field
import random
from requestcompletion.nodes.library import ToolCallLLM
from requestcompletion.llm import SystemMessage

from tests.unit_tests.llm.conftest import MockLLM
# ============ Model ===========

@pytest.fixture
def mock_llm():
    return MockLLM

@pytest.fixture
def model():
    return rc.llm.OpenAILLM("gpt-4o")

# ============ Output Models ===========

class SimpleOutput(BaseModel):
    text: str = Field(description="The text to return")
    number: int = Field(description="The number to return")

class TravelPlannerOutput(BaseModel):
    travel_plan: str = Field(description="The travel plan")
    Total_cost: float = Field(description="The total cost of the trip")
    Currency: str = Field(description="The currency used for the trip")

class MathOutput(BaseModel):
    sum: float = Field(description="The sum of the random numbers")
    random_numbers: List[int] = Field(description="The list of random numbers generated")

class EmptyModel(BaseModel):
    pass

class PersonOutput(BaseModel):
    name: str = Field(description="The name of the person")
    age: int = Field(description="The age of the person")
    Favourites: SimpleOutput = Field(description="The favourite text and number of the person")

@pytest.fixture
def simple_output_model():
    return SimpleOutput

@pytest.fixture
def travel_planner_output_model():
    return TravelPlannerOutput

@pytest.fixture
def math_output_model():
    return MathOutput

@pytest.fixture
def empty_output_model():
    return EmptyModel

@pytest.fixture
def person_output_model():
    return PersonOutput

# ============ Context Variables ===========
@pytest.fixture
def reset_tools_called():
    def _reset(val=0):
        rc.context.put("tools_called", val)
    return _reset

def _increment_tools_called():
    """Increments the tools_called context variable by 1"""
    count = rc.context.get("tools_called", -1)
    rc.context.put("tools_called", count + 1)

# ============ Tools ===========
@pytest.fixture
def simple_tools():
    def random_number() -> int:
        _increment_tools_called()
        return random.randint(1, 100)
    return random_number

@pytest.fixture
def travel_planner_tools():
    def available_locations() -> List[str]:
        _increment_tools_called()
        return [
            "New York", "Los Angeles", "Chicago", "Delhi", "Mumbai", "Bangalore",
            "Paris", "Denmark", "Sweden", "Norway", "Germany"
        ]
    def currency_used(location: str) -> str:
        _increment_tools_called()
        currency_map = {
            "New York": "USD", "Los Angeles": "USD", "Chicago": "USD",
            "Delhi": "INR", "Mumbai": "INR", "Bangalore": "INR",
            "Paris": "EUR", "Denmark": "EUR", "Sweden": "EUR",
            "Norway": "EUR", "Germany": "EUR",
        }
        used_currency = currency_map.get(location)
        if used_currency is None:
            raise ValueError(f"Currency not available for location: {location}")
        return used_currency
    def average_location_cost(location: str, num_days: int) -> float:
        _increment_tools_called()
        daily_costs = {
            "New York": 200.0, "Los Angeles": 180.0, "Chicago": 150.0,
            "Delhi": 50.0, "Mumbai": 55.0, "Bangalore": 60.0,
            "Paris": 220.0, "Denmark": 250.0, "Sweden": 240.0,
            "Norway": 230.0, "Germany": 210.0,
        }
        daily_cost = daily_costs.get(location)
        if daily_cost is None:
            raise ValueError(f"Cost information not available for location: {location}")
        return daily_cost * num_days
    def convert_currency(amount: float, from_currency: str, to_currency: str) -> float:
        _increment_tools_called()
        exchange_rates = {
            ("USD", "EUR"): 0.85, ("EUR", "USD"): 1.1765,
            ("USD", "INR"): 83.0, ("INR", "USD"): 0.01205,
            ("EUR", "INR"): 98.0, ("INR", "EUR"): 0.0102,
        }
        rate = exchange_rates.get((from_currency, to_currency))
        if rate is None:
            raise ValueError("Exchange rate not available")
        return amount * rate
    return convert_currency, available_locations, currency_used, average_location_cost

# ============ Node Fixtures (DRY) ===========

def _make_node(fixture_name, system_message, model, schema, tool_nodes, class_type=None):
    if fixture_name == "easy_wrapper":
        return rc.library.structured_tool_call_llm(
            connected_nodes=tool_nodes,
            pretty_name=schema.__name__ + " Node",
            system_message=system_message,
            llm_model=model,
            schema=schema,
        )
    elif fixture_name == "class_based":
        class CustomNode(rc.library.StructuredToolCallLLM if class_type is None else class_type):
            def __init__(self, message_history, model=model):
                message_history = [x for x in message_history if x.role != "system"]
                message_history.insert(0, SystemMessage(system_message) if isinstance(system_message, str) else system_message)
                super().__init__(
                    message_history=message_history,
                    llm_model=model,
                )
            @classmethod
            def schema(cls):
                return schema
            @classmethod
            def connected_nodes(cls):
                return tool_nodes
            @classmethod
            def pretty_name(cls):
                return schema.__name__ + " Node"
            @classmethod
            def get_llm_model(cls):
                return model() if callable(model) else model
        return CustomNode
    else:
        raise ValueError(f"Unknown node fixture: {fixture_name}")

@pytest.fixture
def simple_node(request, model, simple_output_model):
    system_simple = "Return a simple text and number. Don't use any tools."
    fixture_name = request.param
    tool_nodes = {rc.library.from_function(random.random)}
    return _make_node(fixture_name, system_simple, model, simple_output_model, tool_nodes)

@pytest.fixture
def travel_planner_node(request, model, travel_planner_tools, travel_planner_output_model):
    fixture_name = request.param
    convert_currency, available_locations, currency_used, average_location_cost = travel_planner_tools
    system_travel_planner = "You are a travel planner that will plan a trip. you have access to AvailableLocations, ConvertCurrency, CurrencyUsed and AverageLocationCost tools. Use them when you need to."
    tool_nodes = {
        rc.library.from_function(convert_currency),
        rc.library.from_function(available_locations),
        rc.library.from_function(currency_used),
        rc.library.from_function(average_location_cost),
    }
    return _make_node(fixture_name, system_travel_planner, model, travel_planner_output_model, tool_nodes)

@pytest.fixture
def math_node(request, model, math_output_model):
    system_math_genius = "You are a math genius that calls the RNG tool to generate 5 random numbers between 1 and 100 and gives the sum of those numbers."
    rng_node = rc.library.terminal_llm(
        pretty_name="RNG Tool",
        system_message= "You are a helful assistant that can generate 5 random numbers between 1 and 100.",
        llm_model=model,
        tool_details="A tool used to generate 5 random integers between 1 and 100.",
        tool_params=None,
    )
    fixture_name = request.param
    tool_nodes = {rng_node}
    return _make_node(fixture_name, system_math_genius, model, math_output_model, tool_nodes)

@pytest.fixture
def complex_node(request, model, person_output_model):
    system_complex = "You are an all knowing sentient being. You can answer any question asked to you. You may make up any answer you want. Just provide all info asked for."

    fixture_name = request.param
    tool_nodes = {rc.library.from_function(random.random)}
    return _make_node(fixture_name, system_complex, model, person_output_model, tool_nodes)

# ============ Function-based Node Fixtures ===========

@pytest.fixture
def simple_function_taking_node(model, simple_tools, simple_output_model):
    system_mes = "You are a helpful assistant that uses the random number tool to generate a random number between 1 and 100"

    return rc.library.structured_tool_call_llm(
        connected_nodes={simple_tools},
        pretty_name="Random Number Provider Node",
        system_message=system_mes,
        llm_model=model,
        schema=simple_output_model,
    )

@pytest.fixture
def some_function_taking_travel_planner_node(model, travel_planner_tools, travel_planner_output_model):
    convert_currency, available_locations, currency_used, average_location_cost = travel_planner_tools
    system_travel_planner = "You are a travel planner that will plan a trip. you have access to AvailableLocations, ConvertCurrency, CurrencyUsed and AverageLocationCost tools. Use them when you need to."

    return rc.library.structured_tool_call_llm(
        connected_nodes={
            convert_currency,
            rc.library.from_function(available_locations),
            currency_used,
            rc.library.from_function(average_location_cost),
        },
        pretty_name="Travel Planner Node",
        system_message=system_travel_planner,
        llm_model=model,
        schema=travel_planner_output_model,
    )

@pytest.fixture
def only_function_taking_travel_planner_node(model, travel_planner_tools, travel_planner_output_model):
    convert_currency, available_locations, currency_used, average_location_cost = travel_planner_tools
    system_travel_planner = "You are a travel planner that will plan a trip. you have access to AvailableLocations, ConvertCurrency, CurrencyUsed and AverageLocationCost tools. Use them when you need to."
    return rc.library.structured_tool_call_llm(
        connected_nodes={
            convert_currency,
            available_locations,
            currency_used,
            average_location_cost,
        },
        pretty_name="Travel Planner Node",
        system_message=system_travel_planner,
        llm_model=model,
        schema=travel_planner_output_model,
    )

# ============ Tool Calling LLM Fixtures (max tool calls) ===========

@pytest.fixture
def travel_message_history():
    def _make(msg="I want to travel to New York from Vancouver for 4 days. Give me a budget summary for the trip in INR."):
        return rc.llm.MessageHistory([rc.llm.UserMessage(msg)])
    return _make

@pytest.fixture
def limited_tool_call_node_factory(model, travel_planner_tools):
    def _factory(max_tool_calls=1, system_message=None, tools=None, class_based=False):
        tools = tools or set([rc.library.from_function(tool) for tool in travel_planner_tools])
        sys_msg = system_message or SystemMessage("You are a travel planner that will plan a trip. you have access to AvailableLocations, CurrencyUsed and AverageLocationCost tools. Use them when you need to.")
        tool_nodes = tools
        if not class_based:
            return rc.library.tool_call_llm(
                connected_nodes=tool_nodes,
                pretty_name="Limited Tool Call Test Node",
                system_message=sys_msg,
                llm_model=model,
                max_tool_calls=max_tool_calls,
            )
        else:
            class LimitedToolCallTestNode(ToolCallLLM):
                def __init__(self, message_history, model=model):
                    message_history.insert(0, SystemMessage(sys_msg) if isinstance(sys_msg, str) else sys_msg)
                    super().__init__(message_history, model, max_tool_calls=max_tool_calls)
                @classmethod
                def connected_nodes(cls):
                    return tool_nodes
                @classmethod
                def pretty_name(cls):
                    return "Limited Tool Call Test Node"
            return LimitedToolCallTestNode
    return _factory
