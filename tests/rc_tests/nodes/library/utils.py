from typing import Callable, Set, Type, Tuple, List, Dict, Any

from src.requestcompletion.nodes.library import ToolCallLLM, from_function
from src.requestcompletion.llm import ModelBase, MessageHistory, SystemMessage, UserMessage
from src.requestcompletion.nodes import Node
import src.requestcompletion as rc

def create_top_level_node(test_function: Callable, usr_prompt: str, model_provider: str = "openai") -> ToolCallLLM:
    """
    Creates a top-level node for testing function nodes.
    
    Args:
        test_function: The function to test.
        usr_prompt: The user prompt to use for testing.
        
    Returns:
        A ToolCallLLM node that can be used to test the function.
    """
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
            if model_provider == "openai":
                return rc.llm.OpenAILLM("gpt-4o")
            elif model_provider == "anthropic":
                return rc.llm.AnthropicLLM("claude-3-5-sonnet-20241022")
            else:
                raise ValueError(f"Invalid model provider: {model_provider}")

        @classmethod
        def connected_nodes(cls) -> Set[Type[Node]]:
            return {from_function(test_function)}

        @classmethod
        def pretty_name(cls) -> str:
            return "Top Level Node"

    return TopLevelNode(MessageHistory([UserMessage(usr_prompt)]))