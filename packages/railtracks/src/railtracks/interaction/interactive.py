from __future__ import annotations

from typing import TYPE_CHECKING, Type, TypeVar

from railtracks.built_nodes.llm.response import LLMResponse
from railtracks.nodes.nodes import Node

if TYPE_CHECKING:
    from ..human_in_the_loop.local_chat_ui import UserMessageAttachment

_TOutput = TypeVar("_TOutput", bound=LLMResponse)


def _process_attachment(attachments: list[UserMessageAttachment]) -> list[str]:
    """Processes a list of attachments and returns their data or URLs.

    Args:
        attachments: A list of UserMessageAttachment objects.

    Returns:
        A list of strings containing the processed data or URLs.
    """
    processed = []
    for attachment in attachments:
        if attachment.type == "file":
            processed.append(attachment.data)
        elif attachment.type == "url":
            processed.append(attachment.url)
    return processed


async def _chat_ui_interactive(
    chat_ui,
    node: Type[Node],
    initial_message_to_user: str | None,
    initial_message_to_agent: str | None,
    turns: int | None,
    *args,
    **kwargs,
) -> _TOutput:
    """Handles the interactive session logic using the ChatUI interface.

    Args:
        chat_ui: An instance of the ChatUI class to manage the user interface.
        node: The LLMBase class to interact with.
        initial_message_to_user: An optional message to display to the user at the start of the chat session.
        initial_message_to_agent: An optional message to send to the agent to initiate the conversation.
        turns: The maximum number of conversational turns before the session terminates. If None,
            the session continues until manually closed.
        *args: Additional positional arguments to pass to the node constructor.
        **kwargs: Additional keyword arguments to pass to the node constructor.

    Returns:
        The final output from the node after the interactive session concludes.
    """
    raise NotImplementedError(
        "This function is not yet implemented. Please implement the logic for the interactive session."
    )


async def local_chat(
    node: type[Node],
    initial_message_to_user: str | None = None,
    initial_message_to_agent: str | None = None,
    turns: int | None = None,
    port: int | None = None,
    host: str | None = None,
    auto_open: bool | None = True,
    *args,
    **kwargs,
) -> _TOutput:
    """Starts an interactive session with an LLM-based agent.

    This function launches a local web server, providing a chat interface for
    real-time interaction with a specified `LLMBase` node. It facilitates a
    turn-by-turn conversation with the agent.

    Args:
        node: The `LLMBase` class to interact with.
        initial_message_to_user: An optional message to display to the user
            at the start of the chat session.
        initial_message_to_agent: An optional message to send to the agent to
            initiate the conversation.
        turns: The maximum number of conversational turns before the session
            terminates. If `None`, the session continues until manually closed.
        port: The network port for the web server. If `None`, a random
            available port is selected.
        host: The network host for the web server. Defaults to 'localhost'.
        auto_open: If `True`, automatically opens the chat interface in a
            web browser.
        *args: Additional positional arguments to pass to the node constructor.
        **kwargs: Additional keyword arguments to pass to the node constructor.
            ``interactive_interface`` may be supplied for tests (mock ChatUI class).

    Returns:
        The final output from the node after the interactive session concludes.
        The return type matches the node's `_TOutput` generic type.
    """
    raise NotImplementedError(
        "This function is not yet implemented. Please implement the logic for starting the local chat session."
    )
