import asyncio

from typing import TYPE_CHECKING, Callable, ParamSpec, TypeVar, Type, overload

from ..nodes.nodes import Node
# from .local_chat_ui import ChatUI
from .local_http_chat import ChatUI
from .human_in_the_loop import HIL, HILMessage
from ._call import call
from ..llm.history import MessageHistory
from ..llm.message import UserMessage, AssistantMessage

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")

@overload
async def interactive(
        node: Callable[_P, Node[_TOutput]],
        HIL_interface: Type[ChatUI],
        first_message: str | None = None,
        port: int | None = None,
        host: str | None = None,
        auto_open: bool | None = True,
) -> None: ...

@overload
async def interactive(
        node: Callable[_P, Node[_TOutput]],
        HIL_interface: Type[HIL],
        first_message: str | None = None,
        port: int | None = None,
        host: str | None = None,
        auto_open: bool | None = True,
) -> None: ...

async def interactive(
        node: Callable[_P, Node[_TOutput]],
        HIL_interface: Type[ChatUI] | Type[HIL] = ChatUI,
        first_message: str | None = None,
        port: int | None = None,
        host: str | None = None,
        auto_open: bool | None = True,
) -> None:
    
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
            chat_ui.connect()

            msg_history = MessageHistory([])
            
            while True:
                
                message = await chat_ui.receive_message()
                if message is None or message.content.upper() == "EXIT":
                    chat_ui.disconnect()
                    break

                msg_history.append(UserMessage(message.content))

                response = await call(node, msg_history)

                await chat_ui.send_message(HILMessage(content=response.text))


        except Exception as e:
            print(f"Error during interactive session: {e}")  

    else:
        raise NotImplementedError(f"HIL interface {HIL_interface.__name__} is not yet implemented. Only ChatUI is currently supported.")
