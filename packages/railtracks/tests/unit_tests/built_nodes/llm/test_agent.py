from railtracks import function_node
from railtracks.built_nodes.llm.node import agent_node


def test_agent_node_empty_tool_nodes_with_output_schema(mock_tool_node, mock_schema, mock_llm):
    AgentClass = agent_node(tool_nodes=[mock_tool_node], output_schema=mock_schema, llm=mock_llm)
    assert isinstance(AgentClass, type)

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
        name="MinimalAgent",
        llm=mock_llm,
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