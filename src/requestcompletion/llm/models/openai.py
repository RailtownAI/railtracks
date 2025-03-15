from ._llama_index_wrapper import LlamaWrapper
from llama_index.llms.openai import OpenAI
import json

from ..content import ToolCall
from ..content import ToolCall

class OpenAILLM(LlamaWrapper):
    @classmethod
    def setup_model_object(cls, model_name: str, **kwargs):
        return OpenAI(model_name, **kwargs)

    @classmethod
    def model_type(cls) -> str:
        return "OpenAI"

    @classmethod
    def prepare_tool_calls(cls, tool: ToolCall):
        return {
            "id": tool.identifier,
            "function": {"arguments": json.dumps(tool.arguments), "name": tool.name},
            "type": "function",
        }

    def chat_with_tools(self, messages, tools, **kwargs):
        """
        Chat with the model using tools.
        
        This method preprocesses the kwargs for OpenAI-specific requirements
        before delegating to the parent implementation.
        
        Args:
            messages: The message history to use as context
            tools: The tools to make available to the model
            **kwargs: Additional arguments to pass to the model
            
        Returns:
            A Response object containing the model's response
        """
        # Remove strict parameter if it exists (not supported by OpenAI)
        if "strict" in kwargs:
            del kwargs["strict"]
            
        # Enable parallel tool calls by default for OpenAI
        if "parallel_tool_calls" not in kwargs:
            kwargs["parallel_tool_calls"] = True
            
        # Call the parent implementation
        return super().chat_with_tools(messages, tools, **kwargs)
