from unittest.mock import MagicMock

from pydantic import BaseModel

from railtracks.nodes.nodes import Node
from railtracks.built_nodes.concrete import TerminalLLM, StructuredLLM
from railtracks import agent_node
from railtracks.built_nodes.concrete import StructuredToolCallLLM
from railtracks.built_nodes.concrete import ToolCallLLM


def test_create_new_agent_terminal():
    system_message_text = "hello world"
    model = MagicMock()
    TerminalAgent = agent_node("Terminal_LLM", llm=model, system_message=system_message_text)

    assert issubclass(TerminalAgent, TerminalLLM)
    assert TerminalAgent.get_llm() == model
    assert TerminalAgent.system_message().content == system_message_text
    assert TerminalAgent.name() == "Terminal_LLM"



class TempNode(Node[str]):

    @classmethod
    def name(cls) -> str:
        return "Temp Node"

    async def invoke(self) -> str:
        return "hello world"


def test_create_new_agent_tool_call():
    connected_nodes = {TempNode}
    ToolCallAgent = agent_node(tool_nodes=connected_nodes)

    assert issubclass(ToolCallAgent, ToolCallLLM)
    assert ToolCallAgent.name() == "Tool Call LLM"
    assert ToolCallAgent.tool_nodes() == connected_nodes

class TempModel(BaseModel):
    field1: str
    field2: int

def test_create_new_agent_structured():
    StructuredAgent = agent_node(output_schema=TempModel)

    assert issubclass(StructuredAgent, StructuredLLM)
    assert issubclass(StructuredAgent.output_schema(), TempModel)


def test_create_new_agent_structured_tool_call():
    connected_nodes = {TempNode}
    StructuredToolCallAgent = agent_node(output_schema=TempModel, tool_nodes=connected_nodes)

    assert issubclass(StructuredToolCallAgent, StructuredToolCallLLM)
    assert issubclass(StructuredToolCallAgent.output_schema(), TempModel)
    assert StructuredToolCallAgent.tool_nodes() == connected_nodes

