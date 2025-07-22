import pytest
import railtracks as rt
from railtracks.llm.response import Response
from railtracks.llm import AssistantMessage
from typing import List, Callable, Type
from pydantic import BaseModel, Field

from ...llm.conftest import MockLLM

# =========== Mock model and functions ===========
@pytest.fixture
def mock_llm() -> Type[MockLLM]:
    return MockLLM

@pytest.fixture
def mock_chat_function():
    def _chat(messages):
        return Response(message=AssistantMessage("dummy content"))
    return _chat

@pytest.fixture
def mock_structured_function(simple_output_model):
    def _structured(messages, schema):
        return Response(message=AssistantMessage(simple_output_model(text="dummy content", number=42)))
    return _structured
# ============ System Messages ===========
@pytest.fixture
def encoder_system_message():
    return "You are a text encoder. Encode the input string into bytes and do a random operation on them. You can use the following operations: reverse the byte order, or repeat each byte twice, or jumble the bytes."

@pytest.fixture
def decoder_system_message():
    return "You are a text decoder. Decode the bytes into a string."



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

        class TopLevelNode(rt.library.ToolCallLLM):
            def __init__(self, message_history: rt.llm.MessageHistory):
                message_history.insert(0, rt.llm.SystemMessage(self.system_message()))

                super().__init__(
                    message_history=message_history,
                    model=self.create_model(),
                )

            @classmethod
            def system_message(cls) -> str:
                return "You are a helpful assistant that can call the tools available to you to answer user queries"

            @classmethod
            def create_model(cls):
                if model_provider == "openai":
                    return rt.llm.OpenAILLM("gpt-4o")
                elif model_provider == "anthropic":
                    return rt.llm.AnthropicLLM("claude-3-5-sonnet-20241022")
                else:
                    raise ValueError(f"Invalid model provider: {model_provider}")

            @classmethod
            def connected_nodes(cls):
                return {rt.library.from_function(test_function)}

            @classmethod
            def pretty_name(cls) -> str:
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
