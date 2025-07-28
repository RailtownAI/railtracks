from unittest.mock import MagicMock

from pydantic import BaseModel

from railtracks.nodes.library import TerminalLLM, StructuredLLM
from railtracks.nodes.library.easy_usage_wrappers.one_wrapper import new_agent
from railtracks.nodes.library.tool_calling_llms.structured_tool_call_llm_base import StructuredToolCallLLM
from railtracks.nodes.library.tool_calling_llms.tool_call_llm_base import ToolCallLLM


def test_create_new_agent_terminal():
    system_message_text = "hello world"
    model = MagicMock()
    TerminalAgent = new_agent("Terminal_LLM", llm_model=model, system_message=system_message_text)

    assert isinstance(TerminalAgent, TerminalLLM)
    assert TerminalAgent.llm_model() == model
    assert TerminalAgent.system_message().content == system_message_text
    assert TerminalAgent.pretty_name() == "Terminal_LLM"




def test_create_new_agent_tool_call():
    connected_nodes = {MagicMock()}
    ToolCallAgent = new_agent(connected_nodes=connected_nodes)

    assert isinstance(ToolCallAgent, ToolCallLLM)
    assert ToolCallAgent.pretty_name() == "Tool Call LLM"
    assert ToolCallAgent.connected_nodes() == connected_nodes

class TempModel(BaseModel):
    pass

def test_create_new_agent_structured():
    StructuredAgent = new_agent(schema=TempModel)

    assert isinstance(StructuredAgent, StructuredLLM)
    assert issubclass(StructuredAgent.schema(), TempModel)


def test_create_new_agent_structured_tool_call():
    connected_nodes = {MagicMock()}
    StructuredToolCallAgent = new_agent(schema=TempModel, connected_nodes=connected_nodes)

    assert isinstance(StructuredToolCallAgent, StructuredToolCallLLM)
    assert issubclass(StructuredToolCallAgent.schema(), TempModel)
    assert StructuredToolCallAgent.connected_nodes() == connected_nodes