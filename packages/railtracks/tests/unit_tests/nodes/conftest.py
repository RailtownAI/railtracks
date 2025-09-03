import pytest
from unittest.mock import patch
from railtracks.llm import SystemMessage

# ================= START Fixtures ============
class DummyNode:
    pass

class DummyLLMBase(DummyNode):  # Simulates LLMBase
    @classmethod
    def prepare_tool_message_history(cls, tool_parameters, tool_params=None):
        return f"history-{tool_parameters}-{tool_params}"

class DummyFunctionNode(DummyNode):  # Simulates DynamicFunctionNode
    pass

class DummyOutputLessToolCallLLM(DummyNode):  # Simulates OutputLessToolCallLLM
    pass

class DummyParameter:
    def __init__(self, name):
        self.name = name

class DummyChatUI:
    def __init__(self):
        self.started = False
    def start_server_async(self):
        self.started = True

class DummyTool:
    @staticmethod
    def from_function(func, details=None, params=None):
        return (func, details, params)  # tuple for testing

@pytest.fixture
def dummy_node_class():
    return DummyNode

@pytest.fixture
def patch_node():
    patcher = patch("railtracks.built_nodes._node_builder.Node", DummyNode)
    patcher.start()
    yield DummyNode
    patcher.stop()

@pytest.fixture
def patch_llm_base():
    patcher = patch("railtracks.built_nodes._node_builder.LLMBase", DummyLLMBase)
    patcher.start()
    yield DummyLLMBase
    patcher.stop()

@pytest.fixture
def patch_outputless_toolcall_llm():
    patcher = patch("railtracks.built_nodes._node_builder.OutputLessToolCallLLM", DummyOutputLessToolCallLLM)
    patcher.start()
    yield DummyOutputLessToolCallLLM
    patcher.stop()

@pytest.fixture
def patch_function_node():
    patcher = patch("railtracks.built_nodes._node_builder.DynamicFunctionNode", DummyFunctionNode)
    patcher.start()
    yield DummyFunctionNode
    patcher.stop()

@pytest.fixture
def dummy_parameter():
    return DummyParameter("paramA")

@pytest.fixture
def dummy_tool(monkeypatch):
    # Patch in DummyTool for Tool if needed
    yield DummyTool

@pytest.fixture
def dummy_system_message():
    return SystemMessage("DummySystemMessage")

@pytest.fixture
def dummy_chat_ui():
    return DummyChatUI()