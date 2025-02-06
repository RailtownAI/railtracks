from ._llama_index_wrapper import LlamaWrapper
from llama_index.llms.openai import OpenAI
import openai
import json

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
        kwargs["strict"] = True
        return super().chat_with_tools(messages, tools, **kwargs)
