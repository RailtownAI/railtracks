import pytest
from railtracks.built_nodes.easy_usage_wrappers.agent import agent_node

def test_agent_node_returns_class(mock_tool_node, mock_llm):
    node_cls = agent_node(
        tool_nodes={mock_tool_node},
        llm=mock_llm,
        pretty_name="AgentNode",
        system_message="system"
    )
    assert isinstance(node_cls, type)
    assert hasattr(node_cls, "invoke") or hasattr(node_cls, "__call__")
    assert node_cls.__name__ == "AgentNode"