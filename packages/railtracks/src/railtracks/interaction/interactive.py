import asyncio
import os

from typing import TYPE_CHECKING, Callable, ParamSpec, TypeVar, Type, overload

from ..nodes.nodes import Node
from .local_chat_ui import ChatUI
from .human_in_the_loop import HIL, HILMessage
from ._call import call
from ..llm.history import MessageHistory
from ..llm.message import UserMessage, Role
from ..utils.logging.create import get_rt_logger

logger = get_rt_logger("Interactive")

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")


@overload
async def interactive(
    node: Callable[_P, Node[_TOutput]],
    HIL_interface: Type[ChatUI],
    port: int | None = None,
    host: str | None = None,
    auto_open: bool | None = True,
) -> _TOutput: ...


@overload
async def interactive(
    node: Callable[_P, Node[_TOutput]],
    HIL_interface: Type[HIL],
    port: int | None = None,
    host: str | None = None,
    auto_open: bool | None = True,
) -> _TOutput: ...


async def interactive(
    node: Callable[_P, Node[_TOutput]],
    HIL_interface: Type[ChatUI] | Type[HIL] = ChatUI,
    port: int | None = None,
    host: str | None = None,
    auto_open: bool | None = True,
) -> str:#_TOutput:

    chat_ui_kwargs = {}
    if port is not None:
        chat_ui_kwargs["port"] = port
    if host is not None:
        chat_ui_kwargs["host"] = host
    if auto_open is not None:
        chat_ui_kwargs["auto_open"] = auto_open

    if HIL_interface is ChatUI:
        chat_ui = HIL_interface(**chat_ui_kwargs)

        try:
            logger.info(f"Launching Local ChatUI {os.getpid()}")
            await chat_ui.connect()
            msg_history = MessageHistory([])
            last_tool_idx = 0  # To track the last processed tool response, not sure how efficient this makes things

            while chat_ui.is_connected:

                message = await chat_ui.receive_message()
                if message is None:
                    continue # This should exit the loop since is_connected will be false

                msg_history.append(UserMessage(message.content))

                response = await call(node, msg_history)
                msg_history = response.message_history.copy()

                await chat_ui.send_message(HILMessage(content=response.text))
                for tc, tr in response.tool_invocations[last_tool_idx:]:

                    success = not tr.result.startswith(
                        "There was an error running the tool"
                    )

                    await chat_ui.update_tools(
                        tool_name=tc.name,
                        tool_id=tc.identifier,
                        arguments=tc.arguments,
                        result=str(tr.result),
                        success=success,
                    )

                last_tool_idx = len(response.tool_invocations)

            logger.info("ChatUI session ended.")
        except Exception as e:
            logger.error(f"Error during interactive session: {e}")

    else:
        raise NotImplementedError(
            f"HIL interface {HIL_interface.__name__} is not yet implemented. Only ChatUI is currently supported."
        )
