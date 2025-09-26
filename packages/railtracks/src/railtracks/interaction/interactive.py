from typing import Callable, ParamSpec, Type, TypeVar

from ..built_nodes.concrete._llm_base import LLMBase
from ..human_in_the_loop import HIL, ChatUI, HILMessage
from ..llm.history import MessageHistory
from ..llm.message import UserMessage, AssistantMessage
from ..utils.logging.create import get_rt_logger
from ._call import call

logger = get_rt_logger("Interactive")

_TOutput = TypeVar("_TOutput")


async def interactive(
    node: type[LLMBase[_TOutput]],
    interactive_interface: Type[ChatUI] | Type[HIL] = ChatUI,
    initial_message_to_user: str | None = None,
    initial_message_to_agent: str | None = None,
    port: int | None = None,
    host: str | None = None,
    auto_open: bool | None = True,
    *args,
    **kwargs,
) -> _TOutput:
    """
    An interactive session with a LLMBase child node. Default behaviour will launch a local web server
    and provide a chat interface for interacting with the node.

    Args:
        node (Callable): The node to interact with. This should be a callable that returns a
            Node instance, typically an agent node.
        interactive_interface (Type[ChatUI] | Type[HIL]): The type of interactive interface to use.
            Currently only ChatUI is supported.
        port (int | None): The port to run the interactive interface on. If None, a random port will be chosen.
        host (str | None): The host to run the interactive interface on. If None, 'localhost' will be used.
        auto_open (bool | None): Whether to automatically open the interactive interface in a web browser.
        *args: Additional positional arguments to pass to the node.
        **kwargs: Additional keyword arguments to pass to the node.

        Returns:
        LLMResponse: The final response from the node after the interactive session ends.

    """

    chat_ui_kwargs = {}
    if port is not None:
        chat_ui_kwargs["port"] = port
    if host is not None:
        chat_ui_kwargs["host"] = host
    if auto_open is not None:
        chat_ui_kwargs["auto_open"] = auto_open

    if interactive_interface is ChatUI:
        if not issubclass(node, LLMBase):
            raise ValueError(
                "Interactive sessions only support nodes that are children of LLMBase."
            )
        try:
            logger.info("Connecting with Local Chat Session")
            chat_ui = interactive_interface(**chat_ui_kwargs)
            msg_history = MessageHistory([])
            await chat_ui.connect()

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

                msg_history.append(UserMessage(message.content))

                response = await call(node, msg_history, *args, **kwargs)

                msg_history = response.message_history.copy()

                await chat_ui.send_message(HILMessage(content=response.content))
                await chat_ui.update_tools(response.tool_invocations[last_tool_idx:])

                last_tool_idx = len(response.tool_invocations)

            logger.info("Ended Local Chat Session")
        except Exception as e:
            logger.error(f"Error during interactive session: {e}")
        finally:
            return response # type: ignore

    else:
        raise NotImplementedError(
            f"HIL interface {interactive_interface.__name__} is not yet implemented. Only ChatUI is currently supported."
        )
