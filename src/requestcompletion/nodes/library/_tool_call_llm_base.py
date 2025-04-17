import asyncio
from typing import TypeVar, Generic, Set, Type, Dict, Any
from copy import deepcopy
from ..nodes import Node
from ...llm import MessageHistory, ModelBase, ToolCall, ToolResponse, ToolMessage, UserMessage
from ...interaction.call import call
from abc import ABC, abstractmethod
from ...exceptions import FatalError


_T = TypeVar("_T")

class OutputLessToolCallLLM(Node[_T], ABC, Generic[_T]):
    """A base class that is a node which contains
     an LLm that can make tool calls. The tool calls will be returned
    as calls or if there is a response, the response will be returned as an output"""

    def __init__(
        self,
        message_history: MessageHistory,
        model: ModelBase,
    ):
        super().__init__()
        self.model = model
        self.message_hist = deepcopy(message_history)
        self.structured_resp_node = None    # The structured LLM node

    @abstractmethod
    def connected_nodes(self) -> Set[Type[Node]]: ...

    def create_node(self, tool_name: str, arguments: Dict[str, Any]) -> Node:
        """
        A function which creates a new instance of a node from a tool name and arguments.

        This function may be overwritten to fit the needs of the given node as needed.
        """
        node = [x for x in self.connected_nodes() if x.tool_info().name == tool_name]
        if node is []:
            raise RuntimeError(f"Tool {tool_name} cannot be create a node")
        if len(node) > 1:
            raise FatalError(
                f"Tool {tool_name} has multiple nodes, this is not allowed. Current Node include {[x.tool_info().name for x in self.connected_nodes()]}",
            )
        return node[0].prepare_tool(arguments)

    def tools(self):
        return [x.tool_info() for x in self.connected_nodes()]

    @abstractmethod
    def return_output(self) -> _T: ...

    async def invoke(
        self,
    ) -> _T:
        while True:
            # collect the response from the model
            returned_mess = self.model.chat_with_tools(self.message_hist, tools=self.tools())
            self.message_hist.append(returned_mess.message)

            if returned_mess.message.role == "assistant":
                # if the returned item is a list then it is a list of tool calls
                if isinstance(returned_mess.message.content, list):
                    assert all([isinstance(x, ToolCall) for x in returned_mess.message.content])
                    contracts = [
                        call(lambda arguments: self.create_node(tool_name=t_c.name, arguments=arguments), t_c.arguments)
                        for t_c in returned_mess.message.content
                    ]

                    tool_responses = await asyncio.gather(*contracts, return_exceptions=True)
                    tool_responses = [
                        x if not isinstance(x, Exception) else f"There was an error running the tool: \n Exception message: {x} "
                        for x in tool_responses
                    ]

                    for r_id, resp in zip(
                        [x.identifier for x in returned_mess.message.content],
                        tool_responses,
                    ):
                        self.message_hist.append(ToolMessage(ToolResponse(identifier=r_id, result=str(resp))))

                elif returned_mess.message.content is not None:
                    # this means the tool call is finished
                    break
            else:
                # the message is malformed from the model
                raise RuntimeError("ModelLLM returned an unexpected message type.",
                )
        
        if self.structured_resp_node:
            last_message = self.message_hist[-1]
            try:
                self.structured_output =  await call(
                    self.structured_resp_node, message_history=MessageHistory([UserMessage(last_message.content)])
                )
            except Exception as e:
                self.structured_output = ValueError(f"Failed to parse assistant response into structured output: {e}")
        
        return self.return_output()


