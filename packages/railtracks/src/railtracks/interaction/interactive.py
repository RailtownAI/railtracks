
from typing import Callable, ParamSpec, TypeVar, Type, overload

from ..nodes.nodes import Node
from .local_chat_ui import ChatUI
from .human_in_the_loop import HIL
from ._call import call

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")

@overload
async def interactive(
        node: Callable[_P, Node[_TOutput]],
        HIL_interface: Type[ChatUI],
        port: int | None = None,
        host: str | None = None,
        auto_open: bool | None = True,
) -> None: ...

@overload
async def interactive(
        node: Callable[_P, Node[_TOutput]],
        HIL_interface: Type[HIL],
        port: int | None = None,
        host: str | None = None,
        auto_open: bool | None = True,
) -> None: ...

async def interactive(
        node: Callable[_P, Node[_TOutput]],
        HIL_interface: Type[ChatUI] | Type[HIL] = ChatUI,
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

            first_message = await chat_ui.receive_message()

            print(f"Got first message: {first_message}")
        except Exception as e:
            print(f"Error during interactive session: {e}")  
        finally:
            # Always disconnect to clean up resources
            chat_ui.disconnect()
    else:
        raise NotImplementedError(f"HIL interface {HIL_interface.__name__} is not yet implemented. Only ChatUI is currently supported.")
