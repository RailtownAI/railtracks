import pytest
from railtracks.built_nodes.easy_usage_wrappers.agent import agent_node

def test_agent_node_tool_nodes_and_output_schema(mock_tool_node, mock_llm, mock_schema, mock_sys_mes):
    node_cls = agent_node(
        name="AgentWithToolsAndSchema",
        tool_nodes={mock_tool_node},
        output_schema=mock_schema,
        llm=mock_llm,
        system_message=mock_sys_mes
    )
    assert isinstance(node_cls, type)
    assert node_cls.__name__ == "AgentWithToolsAndSchema"

def test_agent_node_tool_nodes_only(mock_tool_node, mock_llm, mock_sys_mes):
    node_cls = agent_node(
        name="AgentWithToolsOnly",
        tool_nodes={mock_tool_node},
        llm=mock_llm,
        system_message=mock_sys_mes
    )
    assert isinstance(node_cls, type)
    assert node_cls.__name__ == "AgentWithToolsOnly"

def test_agent_node_output_schema_only(mock_llm, mock_schema, mock_sys_mes):
    node_cls = agent_node(
        name="AgentWithSchemaOnly",
        output_schema=mock_schema,
        llm=mock_llm,
        system_message=mock_sys_mes
    )
    assert isinstance(node_cls, type)
    assert node_cls.__name__ == "AgentWithSchemaOnly"

def test_agent_node_minimal():
    node_cls = agent_node(
        name="MinimalAgent"
    )
    assert isinstance(node_cls, type)
    assert node_cls.__name__ == "MinimalAgent"

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
    assert node_cls.__name__ == "AgentWithManifest"

def test_agent_node_tool_nodes_func(mock_llm, mock_function, mock_sys_mes):
    node_cls = agent_node(
        name="AgentWithFuncTool",
        tool_nodes=[mock_function],
        llm=mock_llm,
        system_message=mock_sys_mes
    )
    assert isinstance(node_cls, type)
    assert node_cls.__name__ == "AgentWithFuncTool"