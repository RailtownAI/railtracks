from typing import Callable, Set, Type

import pytest

import requestcompletion as rc
from src.requestcompletion.nodes.library import ToolCallLLM, FunctionNode
from requestcompletion.llm import ModelBase
from requestcompletion.nodes import Node

from dotenv import load_dotenv
load_dotenv()

def simple_function(input_num: int) -> str:
    """
    Simple function that returns the magic number for a given input number
    Args:
        x: The input value to be incremented.
    Returns:
        The input value plus one.
    """
    return str(input_num)*input_num

def top_level_node(test_function: Callable, usr_prompt: str):
    class TopLevelNode(rc.nodes.library.ToolCallLLM):
        def __init__(self, message_history: rc.llm.MessageHistory):
            message_history.insert(0, rc.llm.SystemMessage(self.system_message()))

            super().__init__(
                message_history=message_history,
                model=self.create_model(),
            )

        @classmethod
        def system_message(cls) -> str:
            return "You are a helpful assistant that can call the tools available to you to answer user queries"
            # return "You are a helpful assistant"
            
        @classmethod
        def create_model(cls) -> ModelBase:
            return rc.llm.OpenAILLM("gpt-4o")

        @classmethod
        def connected_nodes(cls) -> Set[Type[Node]]:
            return {FunctionNode(test_function)}
        
        @classmethod
        def pretty_name(cls) -> str:
            return "Top Level Node"

    return TopLevelNode(rc.llm.MessageHistory([rc.llm.UserMessage(usr_prompt)]))

def test_simple_function():
    user_prompt = "What is the magic number for 6?"

    agent = top_level_node(simple_function, user_prompt)

    response = rc.run.run(agent)
    print(response.answer)

if __name__=='__main__':
    test_simple_function()