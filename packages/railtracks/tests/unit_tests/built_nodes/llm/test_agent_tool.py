"""Unit tests for how an agent presents itself when another agent uses it as a tool (#1156)."""

import pytest
from railtracks import ToolManifest
from railtracks.built_nodes.llm.node import agent_node
from railtracks.exceptions.errors import NodeCreationError
from railtracks.llm import MessageHistory, Parameter, SystemMessage

# --- default tool from the system message ---


def test_agent_without_manifest_gets_a_default_tool(mock_llm):
    agent = agent_node(
        "Weather Agent",
        llm=mock_llm,
        system_message="You find the weather for a city.",
    )

    tool = agent.tool_info()

    assert tool.name == "Weather_Agent"
    assert '"Weather Agent"' in tool.detail
    assert tool.detail.endswith("You find the weather for a city.")
    assert [(p.name, p.param_type, p.required) for p in tool.parameters or []] == [
        ("request", "string", True)
    ]


def test_default_tool_accepts_a_system_message_object(mock_llm):
    agent = agent_node(
        "Agent", llm=mock_llm, system_message=SystemMessage("Summarise text.")
    )

    assert agent.tool_info().detail.endswith("Summarise text.")


def test_default_tool_keeps_template_placeholders_as_written(mock_llm):
    agent = agent_node("Agent", llm=mock_llm, system_message="Greet {user_name}.")

    assert "Greet {user_name}." in agent.tool_info().detail


def test_default_tool_keeps_a_long_system_message_whole(mock_llm):
    system_message = "Follow the house style. " * 200

    agent = agent_node("Agent", llm=mock_llm, system_message=system_message)

    assert agent.tool_info().detail.endswith(system_message)


def test_structured_output_agent_gets_a_default_tool(mock_llm, mock_schema):
    agent = agent_node(
        "Extractor",
        llm=mock_llm,
        output_schema=mock_schema,
        system_message="Extract x from the text.",
    )

    assert agent.tool_info().name == "Extractor"


@pytest.mark.parametrize("system_message", [None, "", "   "])
def test_agent_without_manifest_or_system_message_fails_only_as_a_tool(
    mock_llm, system_message
):
    agent = agent_node("Loner", llm=mock_llm, system_message=system_message)

    with pytest.raises(NodeCreationError, match="Loner"):
        agent.tool_info()
    with pytest.raises(NodeCreationError, match="Loner"):
        agent_node("Parent", llm=mock_llm, tool_nodes=[agent])


# --- explicit manifests ---


def test_manifest_description_and_parameters_are_used_as_given(mock_llm):
    manifest = ToolManifest(
        description="Looks up a city's weather.",
        parameters=[Parameter(name="city", description="d", param_type="string")],
    )

    agent = agent_node(
        "Weather", llm=mock_llm, system_message="ignored", manifest=manifest
    )

    tool = agent.tool_info()
    assert tool.detail == "Looks up a city's weather."
    assert [p.name for p in tool.parameters or []] == ["city"]


def test_manifest_without_parameters_gets_the_request_parameter(mock_llm):
    agent = agent_node(
        "Joker", llm=mock_llm, manifest=ToolManifest(description="Tells a joke.")
    )

    tool = agent.tool_info()
    assert tool.detail == "Tells a joke."
    assert [p.name for p in tool.parameters or []] == ["request"]


@pytest.mark.parametrize("description", ["", "   "])
def test_manifest_with_a_blank_description_raises_at_creation(mock_llm, description):
    with pytest.raises(NodeCreationError, match="blank description"):
        agent_node("Agent", llm=mock_llm, manifest=ToolManifest(description))


def test_manifest_parameters_without_a_description_raise_at_creation(mock_llm):
    manifest = ToolManifest(
        description="",
        parameters=[Parameter(name="x", description="d", param_type="string")],
    )

    with pytest.raises(NodeCreationError):
        agent_node("Agent", llm=mock_llm, manifest=manifest)


# --- turning a tool call into the agent's input ---


def test_request_is_passed_through_as_the_user_input(mock_llm):
    agent = agent_node("Agent", llm=mock_llm, system_message="s")

    assert agent.prepare_args(request="Find the weather in Paris") == {
        "user_input": "Find the weather in Paris"
    }


def test_missing_request_raises(mock_llm):
    agent = agent_node("Agent", llm=mock_llm, system_message="s")

    with pytest.raises(TypeError, match="request"):
        agent.prepare_args()


def test_manifest_parameters_are_formatted_into_one_message(mock_llm):
    manifest = ToolManifest(
        description="Looks up a city's weather.",
        parameters=[Parameter(name="city", description="d", param_type="string")],
    )
    agent = agent_node("Weather", llm=mock_llm, manifest=manifest)

    user_input = agent.prepare_args(city="Paris")["user_input"]

    assert isinstance(user_input, MessageHistory)
    assert "city: Paris" in user_input[0].content


# --- tool names ---


def test_agent_tool_name_is_made_provider_safe(mock_llm):
    agent = agent_node("Weather Bot 2.0!", llm=mock_llm, system_message="s")

    assert agent.tool_info().name == "Weather_Bot_2_0_"


def test_unnamed_agents_collide_on_the_default_name(mock_llm):
    first = agent_node(llm=mock_llm, system_message="First.")
    second = agent_node(llm=mock_llm, system_message="Second.")

    with pytest.raises(NodeCreationError, match="LLM_Agent"):
        agent_node("Parent", llm=mock_llm, tool_nodes=[first, second])
