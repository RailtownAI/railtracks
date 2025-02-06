import json

from ._llama_index_wrapper import LlamaWrapper
from llama_index.core import Settings
from llama_index.llms.anthropic import Anthropic

from .. import ToolCall


class AnthropicLLM(LlamaWrapper):
    @classmethod
    def prepare_tool_calls(cls, tool: ToolCall):
        return {
            "id": tool.identifier,
            "input": tool.arguments,
            "name": tool.name,
        }

    @classmethod
    def setup_model_object(cls, model_name: str, **kwargs):
        Settings.tokenizer = Anthropic().tokenizer
        return Anthropic(model_name, **kwargs)

    @classmethod
    def model_type(cls) -> str:
        return "Anthropic"
