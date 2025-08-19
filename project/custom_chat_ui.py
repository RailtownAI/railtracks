import asyncio
from typing import Callable, Set, Type, Union, Iterable

import railtracks as rt
from railtracks.exceptions import LLMError
from railtracks.interaction import call
from railtracks.llm import (
    AssistantMessage,
    MessageHistory,
    ModelBase,
    SystemMessage,
    ToolCall,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from railtracks.llm.message import Role
from railtracks.nodes._node_builder import NodeBuilder
from railtracks.nodes.concrete import ChatToolCallLLM
from railtracks.nodes.nodes import Node
from railtracks.utils.visuals.browser.chat_ui import ChatUI

from project.memory_agent import memory_agent


async def hook_function(message_history: MessageHistory) -> MessageHistory:
    """
    Hook function to inject memory into the user prompt.

    This function asks the memory agent for relevant details and injects it
    into the latest user message.
    """
    # Get the latest user message
    user_message = message_history[-1] if message_history else None

    # If no user message, return as is
    if not user_message:
        return message_history

    # Ask the memory agent for relevant context
    request = (
        f"Here is the user's message: {user_message.content}"
        "\n\n"
        "Please update the project memory with any relevant information from this message."
        "\n"
        "If applicable, search the memory for relevant context that can help answer the user's query."
        "Return anything that is relevant to the user query, or anything that should be considered in creating a response to the message."
        "Otherwise, return an empty string."
    )

    memory_context = await rt.call(memory_agent, request=request)

    print(f"Memory context retrieved: {memory_context}")

    # Inject the memory context into the user message
    if memory_context:
        message_history[-1] = UserMessage(
            content=(
                user_message.content + f"\n\nRelevant Memory Context:\n{memory_context}"
            )
        )

    return message_history


def custom_chatui_node(  # noqa: C901
    tool_nodes: Iterable[Union[Type[Node], Callable]],
    *,
    port: int | None = None,
    host: str | None = None,
    auto_open: bool | None = True,
    pretty_name: str | None = None,
    llm_model: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    user_function_hook = hook_function,
) -> Type[ChatToolCallLLM]:
    """
    Dynamically create a ChatToolCallLLM node class with a web-based chat interface.

    This easy-usage wrapper builds a node class that combines tool-calling LLM capabilities
    with a browser-based chat UI. It allows users to interact with the LLM and connected tools
    through a web interface, making it ideal for interactive demonstrations and testing.

    Args:
        tool_nodes (Set[Union[Type[Node], Callable]]): The set of node classes or callables
            that this LLM can call as tools during conversations.
        port (int, optional): Port number for the web chat interface. If None, a default port
            will be used.
        host (str, optional): Host address for the web chat interface. If None, defaults to
            localhost.
        auto_open (bool, optional): Whether to automatically open the chat interface in the
            default web browser when started. Defaults to True.
        pretty_name (str, optional): Human-readable name for the node/tool displayed in the
            chat interface.
        llm_model (ModelBase, optional): The LLM model instance to use for this node. If not
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

    class CustomChatToolCallLLM(ChatToolCallLLM):
        async def invoke(self):  # noqa: C901
            # If there's no last user message, we need to wait for user input
            if self.message_hist[-1].role != Role.user:
                msg = await self.chat_ui.wait_for_user_input()
                if msg == "EXIT":
                    return self.return_output()
                self.message_hist.append(
                    UserMessage(
                        msg,
                    )
                )

            while True:
                current_tool_calls = len(
                    [m for m in self.message_hist if isinstance(m, ToolMessage)]
                )
                allowed_tool_calls = (
                    self.max_tool_calls - current_tool_calls
                    if self.max_tool_calls is not None
                    else None
                )
                if self.max_tool_calls is not None and allowed_tool_calls <= 0:
                    await self._on_max_tool_calls_exceeded()
                    break

                # collect the response from the model
                returned_mess = self.llm_model.chat_with_tools(
                    self.message_hist, tools=self.tools()
                )

                if returned_mess.message.role == "assistant":
                    # if the returned item is a list then it is a list of tool calls
                    if isinstance(returned_mess.message.content, list):
                        assert all(
                            isinstance(x, ToolCall)
                            for x in returned_mess.message.content
                        )

                        tool_calls = returned_mess.message.content
                        if (
                            allowed_tool_calls is not None
                            and len(tool_calls) > allowed_tool_calls
                        ):
                            tool_calls = tool_calls[:allowed_tool_calls]

                        # append the requested tool calls assistant message, once the tool calls have been verified and truncated (if needed)
                        self.message_hist.append(AssistantMessage(content=tool_calls))

                        contracts = []
                        for t_c in tool_calls:
                            contract = call(
                                self.create_node,
                                t_c.name,
                                t_c.arguments,
                            )
                            contracts.append(contract)

                        tool_responses = await asyncio.gather(
                            *contracts, return_exceptions=True
                        )
                        tool_responses = [
                            (
                                x
                                if not isinstance(x, Exception)
                                else f"There was an error running the tool: \n Exception message: {x} "
                            )
                            for x in tool_responses
                        ]
                        tool_ids = [x.identifier for x in tool_calls]
                        tool_names = [x.name for x in tool_calls]

                        for r_id, r_name, resp in zip(
                            tool_ids,
                            tool_names,
                            tool_responses,
                        ):
                            self.message_hist.append(
                                ToolMessage(
                                    ToolResponse(
                                        identifier=r_id, result=str(resp), name=r_name
                                    )
                                )
                            )

                            # Update the tools tab in the UI
                            success = not isinstance(resp, str) or not resp.startswith(
                                "There was an error running the tool:"
                            )
                            await self.chat_ui.update_tools(
                                tool_name=r_name,
                                tool_id=r_id,
                                arguments=next(
                                    tc.arguments
                                    for tc in tool_calls
                                    if tc.identifier == r_id
                                ),
                                result=str(resp),
                                success=success,
                            )
                    else:
                        assistant_message = returned_mess.message.content

                        self.message_hist.append(
                            AssistantMessage(content=assistant_message)
                        )

                        await self.chat_ui.send_message(assistant_message)

                        user_message = await self.chat_ui.wait_for_user_input()
                        if user_message == "EXIT":
                            break

                        self.message_hist.append(UserMessage(content=user_message))

                        self.message_hist = await user_function_hook(self.message_hist)
                        # print("User message after hook function:" + str(self.message_hist))
                else:
                    # the message is malformed from the model
                    raise LLMError(
                        reason="ModelLLM returned an unexpected message type.",
                        message_history=self.message_hist,
                    )

            return self.return_output()

    builder = NodeBuilder(
        CustomChatToolCallLLM,
        name=pretty_name,
        class_name="LocalChattoolCallLLM",
    )
    builder.llm_base(llm_model, system_message)
    builder.tool_calling_llm(tool_nodes, max_tool_calls)
    builder.chat_ui(chat_ui)

    return builder.build()
