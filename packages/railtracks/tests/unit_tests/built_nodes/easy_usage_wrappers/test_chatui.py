import pytest
from railtracks.built_nodes.easy_usage_wrappers.chatui import chatui_node

def test_chatui_node_returns_class(mock_tool_node, mock_llm):
    node_cls = chatui_node(
        tool_nodes={mock_tool_node},
        port=1234,
        host="127.0.0.1",
        auto_open=False,
        pretty_name="TestNode",
        llm=mock_llm,
        max_tool_calls=2,
        system_message="system"
    )
    # Should be a class type
    assert isinstance(node_cls, type)
    # Should have correct name
    assert node_cls.__name__ == "LocalChattoolCallLLM"
    # Should have expected attributes
    assert hasattr(node_cls, "invoke") or hasattr(node_cls, "__call__")