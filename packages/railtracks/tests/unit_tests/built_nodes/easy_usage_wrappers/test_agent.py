from unittest import mock
import pytest
from railtracks.built_nodes.easy_usage_wrappers.agent import agent_node
from railtracks import ToolManifest
from railtracks.llm import Parameter
from railtracks.built_nodes.concrete import LLMBase
from railtracks.built_nodes._node_builder import NodeBuilder
from railtracks import function_node
class DummyNode(LLMBase):
    @classmethod
    def name(cls): return "DummyNode"
    async def invoke(self): return "dummy"
    @classmethod
    def type(cls): return "Agent"

tool_manifest = ToolManifest(
            description="A tool to be called",
            parameters=[Parameter(
                name="x",
                description="Input to the tool",
                param_type="integer",
            )]
            )

builder = NodeBuilder(DummyNode, name="LLMNode")
params = {tool_manifest.parameters[0]}
builder.tool_callable_llm(tool_details=tool_manifest.description, tool_params=params)
node_cls = builder.build()

def test_agent_node_empty_tool_nodes_with_output_schema(mock_schema, mock_llm):
    # tool_nodes is not None but is empty, output_schema is provided
    AgentClass = agent_node(tool_nodes=[node_cls], output_schema=mock_schema, llm=mock_llm)
    assert AgentClass is not None
    # Should be a structured_llm type (StructuredLLM)
    assert hasattr(AgentClass, 'output_schema')

def test_agent_node_tool_nodes_and_output_schema(mock_tool_node, mock_llm, mock_schema, mock_sys_mes):
    node_cls = agent_node(
        name="AgentWithToolsAndSchema",
        tool_nodes={mock_tool_node},
        output_schema=mock_schema,
        llm=mock_llm,
        system_message=mock_sys_mes
    )
    assert isinstance(node_cls, type)
    assert node_cls.name() == "AgentWithToolsAndSchema"

def test_agent_node_tool_nodes_only(mock_tool_node, mock_llm, mock_sys_mes):
    node_cls = agent_node(
        name="AgentWithToolsOnly",
        tool_nodes={mock_tool_node},
        llm=mock_llm,
        system_message=mock_sys_mes
    )
    assert isinstance(node_cls, type)
    assert node_cls.name() == "AgentWithToolsOnly"

def test_agent_node_output_schema_only(mock_llm, mock_schema, mock_sys_mes):
    node_cls = agent_node(
        name="AgentWithSchemaOnly",
        output_schema=mock_schema,
        llm=mock_llm,
        system_message=mock_sys_mes
    )
    assert isinstance(node_cls, type)
    assert node_cls.name() == "AgentWithSchemaOnly"

def test_agent_node_minimal(mock_llm):
    node_cls = agent_node(
        name="MinimalAgent"
    )
    assert isinstance(node_cls, type)
    assert node_cls.name() == "MinimalAgent"

def test_agent_node_with_manifest(mock_tool_node, mock_llm, mock_manifest, mock_schema, mock_sys_mes):
    node_cls = agent_node(
        name="AgentWithManifest",
        tool_nodes={mock_tool_node},
        output_schema=mock_schema,
        llm=mock_llm,
        system_message=mock_sys_mes,
        manifest=mock_manifest
    )
    assert isinstance(node_cls, type)
    assert node_cls.name() == "AgentWithManifest"

def test_agent_node_tool_nodes_func(mock_llm, mock_function, mock_sys_mes):
    node_cls = agent_node(
        name="AgentWithFuncTool",
        tool_nodes=[function_node(mock_function)],
        llm=mock_llm,
        system_message=mock_sys_mes
    )
    assert isinstance(node_cls, type)
    assert node_cls.name() == "AgentWithFuncTool"


# --- stream= parameter ---

def test_agent_node_stream_false_is_default(mock_llm):
    node_cls = agent_node(name="NoStream", llm=mock_llm)
    assert isinstance(node_cls, type)
    assert node_cls.name() == "NoStream"


def test_agent_node_stream_true_builds_node():
    from unittest.mock import MagicMock
    from railtracks.llm.model import ModelBase
    from typing import Literal
    streaming_llm = MagicMock(spec=ModelBase[Literal[True]])
    streaming_llm.stream = True
    node_cls = agent_node(name="StreamAgent", llm=streaming_llm, stream=True)
    assert isinstance(node_cls, type)
    assert node_cls.name() == "StreamAgent"


def test_agent_node_stream_true_with_schema_builds_node():
    from unittest.mock import MagicMock
    from pydantic import BaseModel
    from railtracks.llm.model import ModelBase
    from typing import Literal

    class MyOutput(BaseModel):
        value: str

    streaming_llm = MagicMock(spec=ModelBase[Literal[True]])
    streaming_llm.stream = True
    node_cls = agent_node(
        name="StreamStructured",
        llm=streaming_llm,
        output_schema=MyOutput,
        stream=True,
    )
    assert isinstance(node_cls, type)
    assert node_cls.name() == "StreamStructured"


def test_agent_node_stream_true_with_tool_nodes_builds_node(mock_function, mock_sys_mes):
    from unittest.mock import MagicMock
    from railtracks.llm.model import ModelBase
    from typing import Literal

    streaming_llm = MagicMock(spec=ModelBase[Literal[True]])
    streaming_llm.stream = True
    node_cls = agent_node(
        name="StreamWithTools",
        llm=streaming_llm,
        tool_nodes=[function_node(mock_function)],
        system_message=mock_sys_mes,
        stream=True,
    )
    assert isinstance(node_cls, type)
    assert node_cls.name() == "StreamWithTools"