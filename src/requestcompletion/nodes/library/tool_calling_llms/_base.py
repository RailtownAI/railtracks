import asyncio
from typing import TypeVar, ParamSpec, Generic, Set, Type, Dict, Any, Union, Callable
from ...nodes import Node
from requestcompletion.llm import (
    MessageHistory,
    ModelBase,
    ToolCall,
    ToolResponse,
    ToolMessage,
    UserMessage,
    AssistantMessage,
)
from .._llm_base import LLMBase
from requestcompletion.run import call
from abc import ABC, abstractmethod
from requestcompletion.exceptions import NodeCreationError, LLMError
from requestcompletion.exceptions.node_invocation.validation import check_max_tool_calls

_T = TypeVar("_T")
_P = ParamSpec("_P")


class OutputLessToolCallLLM(LLMBase[_T], ABC, Generic[_T]):
    """A base class that is a node which contains
     an LLm that can make tool calls. The tool calls will be returned
    as calls or if there is a response, the response will be returned as an output"""

    def __init__(
        self,
        message_history: MessageHistory,
        model: ModelBase,
        max_tool_calls: int | None = 30,
    ):
        super().__init__(model=model, message_history=message_history)
        check_max_tool_calls(max_tool_calls)
        self.structured_resp_node = None  # The structured LLM node
        self.max_tool_calls = max_tool_calls

    @abstractmethod
    def connected_nodes(self) -> Set[Union[Type[Node], Callable]]: ...

    def create_node(self, tool_name: str, arguments: Dict[str, Any]) -> Node:
        """
        A function which creates a new instance of a node Class from a tool name and arguments.

        This function may be overwritten to fit the needs of the given node as needed.
        """
        node = [x for x in self.connected_nodes() if x.tool_info().name == tool_name]
        if node == []:
            raise LLMError(
                reason=f" Error creating a node from tool {tool_name}. The tool_name given by the LLM doesn't match any of the tool names in the connected nodes.",
                message_history=self.message_hist,
            )
        if len(node) > 1:
            raise NodeCreationError(
                message=f"Tool {tool_name} has multiple nodes, this is not allowed. Current Node include {[x.tool_info().name for x in self.connected_nodes()]}",
                notes=["Please check the tool names in the connected nodes."],
            )
        return node[0].prepare_tool(arguments)

    def tools(self):
        return [x.tool_info() for x in self.connected_nodes()]

    @abstractmethod
    def return_output(self) -> _T: ...

    async def _on_max_tool_calls_exceeded(self):
        """force a final response"""
        returned_mess = await self.model.achat_with_tools(self.message_hist, tools=[])
        self.message_hist.append(returned_mess.message)

    async def invoke(self) -> _T:
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
            returned_mess = await self.model.achat_with_tools(
                self.message_hist, tools=self.tools()
            )

            if returned_mess.message.role == "assistant":
                # if the returned item is a list then it is a list of tool calls
                if isinstance(returned_mess.message.content, list):
                    assert all(
                        isinstance(x, ToolCall) for x in returned_mess.message.content
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
                    # this means the tool call is finished
                    self.message_hist.append(
                        AssistantMessage(content=returned_mess.message.content)
                    )
                    break
            else:
                # the message is malformed from the model
                raise LLMError(
                    reason="ModelLLM returned an unexpected message type.",
                    message_history=self.message_hist,
                )

        if self.structured_resp_node:
            try:
                self.structured_output = await call(
                    self.structured_resp_node,
                    message_history=MessageHistory(
                        [UserMessage(str(self.message_hist), inject_prompt=False)]
                    ),
                )
            except Exception:
                # will be raised in the return_output method in StructuredToolCallLLM
                self.structured_output = LLMError(
                    reason="Failed to parse assistant response into structured output.",
                    message_history=self.message_hist,
                )

        return self.return_output()
