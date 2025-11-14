from typing import Literal, Type, TypeVar

from railtracks.built_nodes.concrete.response import LLMResponse

from ..built_nodes.concrete._llm_base import LLMBase
from ..human_in_the_loop import ChatUI, HILMessage
from ..human_in_the_loop.local_chat_ui import UserMessageAttachment
from ..llm.history import MessageHistory
from ..llm.message import AssistantMessage, UserMessage
from ..utils.logging.create import get_rt_logger
from ._call import call

logger = get_rt_logger("Interactive")

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
    chat_ui: ChatUI,
    node: Type[LLMBase[_TOutput, _TOutput, Literal[False]]],
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
    msg_history = MessageHistory([])

    if initial_message_to_user is not None:
        await chat_ui.send_message(HILMessage(content=initial_message_to_user))
        msg_history.append(AssistantMessage(content=initial_message_to_user))
    if initial_message_to_agent is not None:
        msg_history.append(UserMessage(content=initial_message_to_agent))

    last_tool_idx = 0  # To track the last processed tool response, not sure how efficient this makes things

    while chat_ui.is_connected:
        message = await chat_ui.receive_message()
        if message is None:
            continue  # could be `break` but I want to ensure chat_ui.is_connected is updated properly

        attachments = []
        if message.attachments is not None:
            attachments = _process_attachment(message.attachments)
        msg_history.append(UserMessage(content=message.content, attachment=attachments))

        response = await call(node, msg_history, *args, **kwargs)

        msg_history = response.message_history.copy()

        await chat_ui.send_message(HILMessage(content=response.content))
        await chat_ui.update_tools(response.tool_invocations[last_tool_idx:])

        last_tool_idx = len(response.tool_invocations)
        if turns is not None:
            turns -= 1
            if turns <= 0:
                await chat_ui.disconnect()

    logger.info("Ended Local Chat Session")

    return response  # type: ignore


async def local_chat(
    node: type[LLMBase[_TOutput, _TOutput, Literal[False]]],
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
        *args: Additional positional arguments to pass to the `node` constructor.
        **kwargs: Additional keyword arguments to pass to the `node` constructor.

    Returns:
        The final output from the node after the interactive session concludes.
        The return type matches the node's `_TOutput` generic type.
    """

    chat_ui_kwargs = {}
    if port is not None:
        chat_ui_kwargs["port"] = port
    if host is not None:
        chat_ui_kwargs["host"] = host
    if auto_open is not None:
        chat_ui_kwargs["auto_open"] = auto_open

    if not issubclass(node, LLMBase):
        raise ValueError(
            "Interactive sessions only support nodes that are children of LLMBase."
        )
    response = None
    try:
        logger.info("Connecting with Local Chat Session")

        chat_ui = ChatUI(**chat_ui_kwargs)

        await chat_ui.connect()

        response = await _chat_ui_interactive(
            chat_ui,
            node,
            initial_message_to_user,
            initial_message_to_agent,
            turns,
            *args,
            **kwargs,
        )

    except Exception as e:
        logger.error(f"Error during interactive session: {e}")
    finally:
        return response  # type: ignore
