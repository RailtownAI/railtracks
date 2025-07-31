import pytest

import railtracks as rt

from railtracks.llm import Parameter
from railtracks.nodes.manifest import ToolManifest
from railtracks.nodes.easy_usage_wrappers.agent import agent_node
from railtracks.nodes.easy_usage_wrappers.helpers import terminal_llm

def test_create_with_manifest():
    param = Parameter(
        name="test_param",
        param_type="string",
        description="A test parameter",
    )
    description = "A test agent with terminal LLM."
    tllm_agent_creation = agent_node(
        name="tllm_agent_creation",
        llm_model=rt.llm.OpenAILLM("gpt-4o"),
        manifest=ToolManifest(
            description=description,
            parameters=[param],
        ),
    )

    tllm_old_creation = terminal_llm(
        name="tllm_old_creation",
        llm_model=rt.llm.OpenAILLM("gpt-4o"),
        tool_details=description,
        tool_params={
            param
        },
    )

    old_tool = tllm_old_creation.tool_info()
    new_tool = tllm_agent_creation.tool_info()

    assert list(old_tool.parameters) == list(new_tool.parameters)
    assert old_tool.detail == new_tool.detail
    assert old_tool.name != new_tool.name


def test_no_manifest():
    agent = agent_node(name="not a tool")
    with pytest.raises(NotImplementedError):
        agent.tool_info()