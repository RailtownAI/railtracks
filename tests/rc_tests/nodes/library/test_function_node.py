from typing import Callable, Set, Type
from pydantic import BaseModel, ConfigDict

from src.requestcompletion.nodes.library import ToolCallLLM, FunctionNode, from_function
from src.requestcompletion.llm import ModelBase, MessageHistory, SystemMessage, UserMessage
from src.requestcompletion.nodes import Node
import src.requestcompletion as rc

from dotenv import load_dotenv


load_dotenv()

class Input(BaseModel):
    name: str
    value: str


def simple_function(input_num: int) -> str:
    """
    Simple function that returns the magic number for a given input number
    Args:
        x: The input value to be incremented.
    Returns:
        The magic number for the given input number.
    """
    return str(input_num) * input_num

def multiline_function(input_num: int) -> str:
    """
    Simple function with
    multi line arguments that return a 
    magic number for a given input number

    Args:
        x: The input value to be
        incremented.

    Returns:
        The magic number for the given input number.
    """
    return str(input_num) * input_num

def custom_type_function(input_: Input) -> str:
    """
    Simple function that returns a magic phrase based on the input value"
    
    Args:
        input (Input): The input to be used in the magic phrase

    Returns:
        (str): The magic phrase
    """
    return f"{str(input_.value)}_{str(input_.name)}_{str(input_.value)}"

def top_level_node(test_function: Callable, usr_prompt: str):
    class TopLevelNode(ToolCallLLM):
        def __init__(self, message_history: MessageHistory):
            message_history.insert(0, SystemMessage(self.system_message()))

            super().__init__(
                message_history=message_history,
                model=self.create_model(),
            )

        @classmethod
        def system_message(cls) -> str:
            return "You are a helpful assistant that can call the tools available to you to answer user queries"

        @classmethod
        def create_model(cls) -> ModelBase:
            return rc.llm.OpenAILLM("gpt-4o")

        @classmethod
        def connected_nodes(cls) -> Set[Type[Node]]:
            return {from_function(test_function)}

        @classmethod
        def pretty_name(cls) -> str:
            return "Top Level Node"

    return TopLevelNode(MessageHistory([UserMessage(usr_prompt)]))


def test_simple_function():
    user_prompt = "What is the magic number for 6?"

    agent = top_level_node(simple_function, user_prompt)

    response = rc.run.run(agent)

    assert "666666" in response.answer

def test_multiline_function():
    user_prompt = "What is the magic number for 6?"

    agent = top_level_node(multiline_function, user_prompt)

    response = rc.run.run(agent)

    assert "666666" in response.answer

def test_custom_type_function():
    user_prompt = "What is the magic phrase for an input with name Aragron and value 13?"

    agent = top_level_node(custom_type_function, user_prompt)
    response = rc.run.run(agent)
    print(response.answer)
    assert "13_Aragron_13" in response.answer

if __name__ == "__main__":
    test_custom_type_function()