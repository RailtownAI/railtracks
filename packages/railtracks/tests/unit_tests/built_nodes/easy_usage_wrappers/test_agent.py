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