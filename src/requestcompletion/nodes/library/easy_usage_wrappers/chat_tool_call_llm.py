import warnings
from typing import Set, Union, Type, Callable, Literal, Dict, Any
from inspect import isclass, isfunction
from copy import deepcopy
import asyncio
from requestcompletion.run import call

from ....nodes.nodes import Node
from ....llm.message import Role
from ..tool_calling_llms._base import OutputLessToolCallLLM
from ....exceptions import NodeCreationError, LLMError
from ....exceptions.node_creation.validation import validate_tool_metadata
from ....nodes.library.function import from_function
from ....exceptions.node_invocation.validation import check_model, check_message_history
from ....llm import (
    ModelBase,
    ToolCall,
    SystemMessage,
    MessageHistory,
    AssistantMessage,
    ToolMessage,
    UserMessage,
    ToolResponse,
)
from ....visuals.browser.chat_ui import ChatUI
from requestcompletion.utils.logging.create import get_rc_logger

def chat_tool_call_llm(
    connected_nodes: Set[Union[Type[Node], Callable]],
    pretty_name: str | None = None,
    model: ModelBase | None = None,
    max_tool_calls: int | None = None,
    system_message: SystemMessage | str | None = None,
    output_type: Literal["MessageHistory", "LastMessage"] = "LastMessage",
) -> Type[OutputLessToolCallLLM[Union[MessageHistory, AssistantMessage]]]:

    output = MessageHistory if output_type == "MessageHistory" else AssistantMessage

    # Converting functions to nodes if needed
    for elem in list(connected_nodes):
        if isclass(elem):
            if not issubclass(elem, Node):
                raise NodeCreationError(
                    message=f"Tools must be of type Node or FunctionType but got {type(elem)}",
                    notes=[
                        "Please make sure you are passing in a function or a Node object to connected_nodes"
                    ],
                )
        elif isfunction(elem):
            connected_nodes.remove(elem)
            connected_nodes.add(from_function(elem))

    chat_ui = ChatUI(port=8000)
    server_address = chat_ui.start_server_async()

    class ChatToolCallLLM(OutputLessToolCallLLM[output]):
        def __init__(
            self,
            message_history: MessageHistory | None = None,
            llm_model: ModelBase | None = None,
            max_tool_calls: int | None = max_tool_calls,
        ):
            check_message_history(message_history, system_message)

            self.logger = get_rc_logger("ChatUI")
            self.logger.info(msg=f"CREATED UI server started at {server_address}")

            message_history_copy = deepcopy(message_history)

            if system_message:
                if len([x for x in message_history_copy if x.role == Role.system]) > 0:
                    warnings.warn(
                        "System message already exists in message history. We will replace it."
                    )
                    message_history_copy = [
                        m for m in message_history_copy if m.role != Role.system
                    ]
                    message_history_copy.insert(0, system_message)
                else:
                    message_history_copy.insert(0, system_message)

            if llm_model:
                if model:
                    warnings.warn(
                        "You have provided a model as a parameter and as a class variable. We will use the parameter."
                    )

            else:
                check_model(model)
                llm_model = model

            self.tool_calls = []
            self.tool_responses = []

            super().__init__(
                message_history_copy,
                llm_model,
                max_tool_calls=max_tool_calls,
            )

        def return_output(self):
            if output_type == "MessageHistory":
                return self.message_hist
            else:
                return self.message_hist[-1]

        async def invoke(self):
            # If there's no last user message, we need to wait for user input
            if self.message_hist[-1].role != Role.user:
                msg = await chat_ui.wait_for_user_input()
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
                returned_mess = self.model.chat_with_tools(
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
                    else:
                        assistant_message = returned_mess.message.content
                        
                        self.message_hist.append(
                            AssistantMessage(content=assistant_message)
                        )
                        await chat_ui.send_message(
                            assistant_message                        )


                        user_message = await chat_ui.wait_for_user_input()
                        if user_message == "EXIT":
                            break
                        self.message_hist.append(
                            UserMessage(content=user_message)
                        )
                else:
                    # the message is malformed from the model
                    raise LLMError(
                        reason="ModelLLM returned an unexpected message type.",
                        message_history=self.message_hist,
                    )

            return self.return_output()

        def connected_nodes(self) -> Set[Union[Type[Node], Callable]]:
            return connected_nodes

        @classmethod
        def pretty_name(cls) -> str:
            if pretty_name is None:
                return (
                    "ChatToolCallLLM("
                    + ", ".join([x.pretty_name() for x in connected_nodes])
                    + ")"
                )
            else:
                return pretty_name

    return ChatToolCallLLM
