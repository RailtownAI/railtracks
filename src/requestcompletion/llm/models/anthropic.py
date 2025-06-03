from typing import List

from ._llama_index_wrapper import LlamaWrapper
from llama_index.core import Settings
from llama_index.llms.anthropic import Anthropic

from .. import ToolCall, MessageHistory, Tool


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

    def chat_with_tools(self, messages: MessageHistory, tools: List[Tool], **kwargs):
        # default to parallel tool calling. Noting the specific keyword that is used here.
        if "allow_parallel_tool_calls" not in kwargs:
            kwargs["allow_parallel_tool_calls"] = True

        super().chat(messages, tools=tools, **kwargs)
