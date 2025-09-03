from typing import Callable, Set, Type, Union

from railtracks.built_nodes._node_builder import NodeBuilder
from railtracks.built_nodes.concrete import ChatToolCallLLM, RTFunction
from railtracks.llm import (
    ModelBase,
    SystemMessage,
)
from railtracks.nodes.nodes import Node
from railtracks.utils.visuals.browser.chat_ui import ChatUI


def chatui_node(
    tool_nodes: Set[Union[Type[Node], Callable | RTFunction]],
    *,
    port: int | None = None,
    host: str | None = None,
    auto_open: bool | None = True,
    pretty_name: str | None = None,
    llm: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
) -> Type[ChatToolCallLLM]:
    """
    Dynamically create a ChatToolCallLLM node class with a web-based chat interface.

    This easy-usage wrapper builds a node class that combines tool-calling LLM capabilities
    with a browser-based chat UI. It allows users to interact with the LLM and connected tools
    through a web interface, making it ideal for interactive demonstrations and testing.

    Args:
        tool_nodes (Set[Union[Type[Node], Callable | RTFunction]]): The set of node classes or callables
            that this LLM can call as tools during conversations.
        port (int, optional): Port number for the web chat interface. If None, a default port
            will be used.
        host (str, optional): Host address for the web chat interface. If None, defaults to
            localhost.
        auto_open (bool, optional): Whether to automatically open the chat interface in the
            default web browser when started. Defaults to True.
        pretty_name (str, optional): Human-readable name for the node/tool displayed in the
            chat interface.
        llm (ModelBase, optional): The LLM model instance to use for this node. If not
            specified, a default model will be used.
        max_tool_calls (int, optional): Maximum number of tool calls allowed per conversation
            turn. If None, unlimited tool calls are allowed.
        system_message (SystemMessage or str, optional): The system prompt/message that defines
            the LLM's behavior and role in the chat interface.

    Returns:
        Type[ChatToolCallLLM]: The dynamically generated node class configured with the specified
            chat interface and tool-calling capabilities.
    """

    kwargs = {}
    if port is not None:
        kwargs["port"] = port
    if host is not None:
        kwargs["host"] = host
    if auto_open is not None:
        kwargs["auto_open"] = auto_open

    chat_ui = ChatUI(**kwargs)

    builder = NodeBuilder(
        ChatToolCallLLM,
        name=pretty_name,
        class_name="LocalChattoolCallLLM",
    )
    builder.llm_base(llm, system_message)
    builder.tool_calling_llm(tool_nodes, max_tool_calls)
    builder.chat_ui(chat_ui)

    return builder.build()
