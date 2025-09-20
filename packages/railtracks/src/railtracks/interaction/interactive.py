import asyncio

from typing import TYPE_CHECKING, Callable, ParamSpec, TypeVar, Type, overload

from ..nodes.nodes import Node
from .local_chat_ui import ChatUI
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
            
            while chat_ui.is_connected:
                
                # message = await chat_ui.receive_message()
                receive_task = asyncio.create_task(chat_ui.receive_message())
                shutdown_task = asyncio.create_task(chat_ui.shutdown_event.wait())
    
                # Wait for either message or shutdown
                done, pending = await asyncio.wait(
                    [receive_task, shutdown_task], 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                
                # Check what completed
                if shutdown_task in done:
                    break  # Clean shutdown
                    
                if receive_task in done:
                    message = receive_task.result()
                    if message is None:  # Handle disconnection
                        break

                msg_history.append(UserMessage(message.content))

                response = await call(node, msg_history)

                await chat_ui.send_message(HILMessage(content=response.text))


        except Exception as e:
            print(f"Error during interactive session: {e}")  
        finally:
            # Always disconnect to clean up resources
            chat_ui.disconnect()
    else:
        raise NotImplementedError(f"HIL interface {HIL_interface.__name__} is not yet implemented. Only ChatUI is currently supported.")
