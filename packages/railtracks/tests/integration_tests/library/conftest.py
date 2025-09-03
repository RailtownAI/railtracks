import pytest
import railtracks as rt
from typing import List, Callable, Type
from pydantic import BaseModel, Field
from railtracks.llm import SystemMessage
import random 

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
            llm=llm,
            tool_nodes={rt.function_node(test_function)},
        )

    return _create_node


# ============ Output Models ===========
class SimpleOutput(BaseModel):  # simple structured output case
    text: str = Field(description="The text to return")
    number: int = Field(description="The number to return")


@pytest.fixture
def simple_output_model():
    return SimpleOutput

# =====================================================

# ============ Context Variables ===========
@pytest.fixture
def _reset_tools_called():
    def _reset(val=0):
        rt.context.put("tools_called", val)
    return _reset

@pytest.fixture
def _increment_tools_called():
    """Increments the tools_called context variable by 1"""
    def _increment():
        count = rt.context.get("tools_called", 0)
        rt.context.put("tools_called", count + 1)
    return _increment