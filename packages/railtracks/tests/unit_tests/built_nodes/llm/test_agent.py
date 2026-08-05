import functools

import pytest
from railtracks import function_node
from railtracks.built_nodes.llm.node import agent_node
from railtracks.exceptions.errors import NodeCreationError


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


# --- tool_nodes() accessor ---

def test_agent_node_tool_nodes_accessor(mock_tool_node, mock_llm):
    node_cls = agent_node("Agent", tool_nodes=[mock_tool_node], llm=mock_llm)
    assert node_cls.tool_nodes() == [mock_tool_node.node_type]


def test_agent_node_tool_nodes_accessor_empty_without_tools(mock_llm):
    node_cls = agent_node("Agent", llm=mock_llm)
    assert node_cls.tool_nodes() == []


def test_agent_node_tool_nodes_resolves_rtfunctions(mock_llm, mock_function):
    rt_func = function_node(mock_function)
    node_cls = agent_node("Agent", tool_nodes=[rt_func], llm=mock_llm)

    # RTFunction entries are resolved to their underlying node type.
    assert node_cls.tool_nodes() == [rt_func.node_type]


def test_agent_node_tool_nodes_returns_every_tool(mock_llm, mock_function):
    # agent_node unpacks tool_nodes into a set, so order is not guaranteed here.
    tools = [function_node(mock_function, name=f"tool_{i}") for i in range(5)]
    node_cls = agent_node("Agent", tool_nodes=tools, llm=mock_llm)
    assert sorted(t.tool_info().name for t in node_cls.tool_nodes()) == [
        f"tool_{i}" for i in range(5)
    ]


def test_agent_node_tool_nodes_dedupes_repeated_entries(mock_tool_node, mock_llm):
    node_cls = agent_node(
        "Agent", tool_nodes=[mock_tool_node, mock_tool_node], llm=mock_llm
    )
    assert node_cls.tool_nodes() == [mock_tool_node.node_type]


def test_agent_node_tool_nodes_is_defensive_copy(mock_tool_node, mock_llm):
    node_cls = agent_node("Agent", tool_nodes=[mock_tool_node], llm=mock_llm)

    node_cls.tool_nodes().clear()

    assert node_cls.tool_nodes() == [mock_tool_node.node_type]


def test_agent_node_tool_nodes_includes_sub_agents(mock_llm, mock_manifest):
    sub_agent = agent_node("SubAgent", llm=mock_llm, manifest=mock_manifest)
    node_cls = agent_node("Agent", tool_nodes=[sub_agent], llm=mock_llm)

    # An agent-as-tool appears in the list like any other node.
    assert node_cls.tool_nodes() == [sub_agent]


def test_agent_node_tool_schemas_derivable_from_tool_nodes(mock_tool_node, mock_llm):
    node_cls = agent_node("Agent", tool_nodes=[mock_tool_node], llm=mock_llm)
    assert [t.tool_info().name for t in node_cls.tool_nodes()] == ["DummyTool"]


# --- duplicate tool names (#1337) ---

def test_agent_node_duplicate_tool_names_raise_at_creation(mock_llm, mock_function):
    square = function_node(mock_function, name="power")
    cube = function_node(mock_function, name="power")

    with pytest.raises(NodeCreationError, match="power"):
        agent_node("Agent", tool_nodes=[square, cube], llm=mock_llm)


def test_agent_node_duplicate_names_from_partials_raise(mock_llm):
    # Partials of one function inherit its name but bind different arguments, so they are
    # different tools that collide. This is the case reported in #1337.
    def power(x: int, exp: int) -> int:
        return x**exp

    with pytest.raises(NodeCreationError, match="power"):
        agent_node(
            "Agent",
            llm=mock_llm,
            tool_nodes=[
                function_node(functools.partial(power, exp=2)),
                function_node(functools.partial(power, exp=3)),
            ],
        )


def test_agent_node_same_function_under_different_names_both_kept(mock_llm, mock_function):
    node_cls = agent_node(
        "Agent",
        llm=mock_llm,
        tool_nodes=[
            function_node(mock_function, name="first"),
            function_node(mock_function, name="second"),
        ],
    )

    # Distinct names are separately addressable, so both survive.
    assert sorted(t.tool_info().name for t in node_cls.tool_nodes()) == [
        "first",
        "second",
    ]


def test_agent_node_distinct_tool_names_are_accepted(mock_llm, mock_function):
    square = function_node(mock_function, name="square")
    cube = function_node(mock_function, name="cube")

    node_cls = agent_node("Agent", tool_nodes=[square, cube], llm=mock_llm)

    assert sorted(t.tool_info().name for t in node_cls.tool_nodes()) == [
        "cube",
        "square",
    ]


def test_agent_node_duplicate_name_against_sub_agent_raises(mock_llm, mock_manifest, mock_function):
    sub_agent = agent_node("collide", llm=mock_llm, manifest=mock_manifest)
    tool = function_node(mock_function, name="collide")

    with pytest.raises(NodeCreationError, match="collide"):
        agent_node("Agent", tool_nodes=[sub_agent, tool], llm=mock_llm)