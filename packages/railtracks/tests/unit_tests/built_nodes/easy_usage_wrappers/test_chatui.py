

import pytest
from unittest.mock import patch, MagicMock
from railtracks.built_nodes.easy_usage_wrappers.chatui import chatui_node

@pytest.fixture(autouse=True)
def mock_chatui_and_nodebuilder():
    with patch("railtracks.built_nodes.easy_usage_wrappers.chatui.ChatUI", MagicMock()), \
         patch("railtracks.built_nodes.easy_usage_wrappers.chatui.NodeBuilder") as mock_builder:
        mock_instance = MagicMock()
        mock_instance.build.return_value = type("MockChatToolCallLLM", (), {})
        mock_builder.return_value = mock_instance
        yield

def test_chatui_node_basic(mock_tool_node, mock_llm):
    node_cls = chatui_node(
        tool_nodes={mock_tool_node},
        llm=mock_llm,
        pretty_name="BasicChatUI"
    )
    assert isinstance(node_cls, type)

def test_chatui_node_with_port_host(mock_tool_node, mock_llm):
    node_cls = chatui_node(
        tool_nodes={mock_tool_node},
        llm=mock_llm,
        port=8080,
        host="127.0.0.1",
        pretty_name="PortHostChatUI"
    )
    assert isinstance(node_cls, type)

def test_chatui_node_auto_open_false(mock_tool_node, mock_llm):
    node_cls = chatui_node(
        tool_nodes={mock_tool_node},
        llm=mock_llm,
        auto_open=False,
        pretty_name="AutoOpenFalseChatUI"
    )
    assert isinstance(node_cls, type)

def test_chatui_node_max_tool_calls(mock_tool_node, mock_llm):
    node_cls = chatui_node(
        tool_nodes={mock_tool_node},
        llm=mock_llm,
        max_tool_calls=3,
        pretty_name="MaxToolCallsChatUI"
    )
    assert isinstance(node_cls, type)

def test_chatui_node_system_message(mock_tool_node, mock_llm, mock_sys_mes):
    node_cls = chatui_node(
        tool_nodes={mock_tool_node},
        llm=mock_llm,
        system_message=mock_sys_mes,
        pretty_name="SystemMessageChatUI"
    )
    assert isinstance(node_cls, type)

def test_chatui_node_multiple_tools(mock_tool_node, mock_llm, mock_function):
    node_cls = chatui_node(
        tool_nodes={mock_tool_node, mock_function},
        llm=mock_llm,
        pretty_name="MultiToolChatUI"
    )
    assert isinstance(node_cls, type)