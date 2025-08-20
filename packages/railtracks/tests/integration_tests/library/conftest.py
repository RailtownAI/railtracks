import pytest
import railtracks as rt
from typing import List, Callable
from pydantic import BaseModel, Field
from railtracks.llm import SystemMessage


# ============ Model ===========
@pytest.fixture
def model():
    return rt.llm.OpenAILLM("gpt-4o")


# ============ System Messages ===========
@pytest.fixture
def encoder_system_message():
    return SystemMessage("You are a text encoder. Encode the input string into bytes and do a random operation on them. You can use the following operations: reverse the byte order, or repeat each byte twice, or jumble the bytes.")


@pytest.fixture
def decoder_system_message():
    return SystemMessage("You are a text decoder. Decode the bytes into a string.")


# ============ Helper function for test_function.py ===========
@pytest.fixture
def _agent_node_factory():
    """
    Returns a top level agent node with mock model for testing 
    """

    def _create_node(test_function: Callable, llm: rt.llm.ModelBase):
        """
        Creates a top-level node for testing function nodes.

        Args:
            test_function: The function to test.
            model_provider: The model provider to use (default: "openai").

        Returns:
            A ToolCallLLM node that can be used to test the function.
        """

        return rt.agent_node(
            name=f"TestNode-{test_function.__name__}",
            system_message=SystemMessage(
                f"You are a test node for the function {test_function.__name__}"
            ),
            llm_model=llm,
            tool_nodes={rt.function_node(test_function)},
        )

    return _create_node


# ============ Output Models ===========
class SimpleOutput(BaseModel):  # simple structured output case
    text: str = Field(description="The text to return")
    number: int = Field(description="The number to return")


class TravelPlannerOutput(BaseModel):  # structured using tool calls
    travel_plan: str = Field(description="The travel plan")
    Total_cost: float = Field(description="The total cost of the trip")
    Currency: str = Field(description="The currency used for the trip")


class MathOutput(BaseModel):  # structured using terminal llm as tool
    sum: float = Field(description="The sum of the random numbers")
    random_numbers: List[int] = Field(
        description="The list of random numbers generated"
    )


class EmptyModel(BaseModel):  # empty structured output case
    pass


class PersonOutput(BaseModel):  # complex structured output case
    name: str = Field(description="The name of the person")
    age: int = Field(description="The age of the person")
    Favourites: SimpleOutput = Field(
        description="The favourite text and number of the person"
    )


@pytest.fixture
def travel_planner_output_model():
    return TravelPlannerOutput


@pytest.fixture
def math_output_model():
    return MathOutput


@pytest.fixture
def simple_output_model():
    return SimpleOutput


@pytest.fixture
def empty_output_model():
    return EmptyModel


@pytest.fixture
def person_output_model():
    return PersonOutput
# =====================================================