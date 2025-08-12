import pytest
import railtracks as rt
from typing import List, Callable
from pydantic import BaseModel, Field
from railtracks.llm import SystemMessage
from railtracks.nodes.concrete import ToolCallLLM


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
def create_top_level_node():
    """
    Returns a factory function that creates top-level nodes for testing.
    """

    def _create_node(test_function: Callable, model_provider: str = "openai"):
        """
        Creates a top-level node for testing function nodes.

        Args:
            test_function: The function to test.
            model_provider: The model provider to use (default: "openai").

        Returns:
            A ToolCallLLM node that can be used to test the function.
        """

        class TopLevelNode(ToolCallLLM):
            def __init__(self, user_input: rt.llm.MessageHistory):
                user_input.insert(0, self.system_message())

                super().__init__(
                    user_input=user_input,
                    llm_model=self.create_model(),
                )

            @classmethod
            def system_message(cls) -> str:
                return SystemMessage("You are a helpful assistant that can call the tools available to you to answer user queries")

            @classmethod
            def create_model(cls):
                if model_provider == "openai":
                    return rt.llm.OpenAILLM("gpt-4o")
                elif model_provider == "anthropic":
                    return rt.llm.AnthropicLLM("claude-3-5-sonnet-20241022")
                else:
                    raise ValueError(f"Invalid model provider: {model_provider}")

            @classmethod
            def tool_nodes(cls):
                return {rt.function_node(test_function).node_type}

            @classmethod
            def name(cls) -> str:
                return "Top Level Node"

        return TopLevelNode

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