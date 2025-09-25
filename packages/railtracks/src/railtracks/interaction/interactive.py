import os
from typing import Callable, ParamSpec, TypeVar, Type, Union

from .local_chat_ui import ChatUI
from .human_in_the_loop import HIL, HILMessage
from ._call import call
from ..llm.history import MessageHistory
from ..llm.message import UserMessage
from ..utils.logging.create import get_rt_logger
from ..built_nodes.concrete.response import LLMResponse
from ..nodes.nodes import Node

logger = get_rt_logger("Interactive")

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")


async def interactive(
    node: Callable[_P, Node[_TOutput]],
    HIL_interface: Type[ChatUI] | Type[HIL] = ChatUI,
    port: int | None = None,
    host: str | None = None,
    auto_open: bool | None = True,
    *args: _P.args,
    **kwargs: dict[str, any],  # I dislike this but it's needed for typing to work
) -> LLMResponse:

    chat_ui_kwargs = {}
    if port is not None:
        chat_ui_kwargs["port"] = port
    if host is not None:
        chat_ui_kwargs["host"] = host
    if auto_open is not None:
        chat_ui_kwargs["auto_open"] = auto_open

    if HIL_interface is ChatUI:
        chat_ui = HIL_interface(**chat_ui_kwargs)
        msg_history = MessageHistory([])
        response = LLMResponse("", msg_history) # typing shenanigans

        try:
            logger.info(f"Connecting with Local Chat Session")
            await chat_ui.connect()
            last_tool_idx = 0  # To track the last processed tool response, not sure how efficient this makes things
            while chat_ui.is_connected:

                message = await chat_ui.receive_message()
                if message is None:
                    continue  # This should exit the loop since is_connected will be false

                msg_history.append(UserMessage(message.content))

                response: LLMResponse = await call(node, msg_history, *args, **kwargs)

                msg_history: MessageHistory = response.message_history.copy()

                await chat_ui.send_message(HILMessage(content=response.content))
                await chat_ui.update_tools(response.tool_invocations[last_tool_idx:])

                last_tool_idx = len(response.tool_invocations)

            logger.info(f"Ended Local Chat Session")
        except Exception as e:
            logger.error(f"Error during interactive session: {e}")
        finally:
            return response

    else:
        raise NotImplementedError(
            f"HIL interface {HIL_interface.__name__} is not yet implemented. Only ChatUI is currently supported."
        )
