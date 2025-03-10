from functools import partial
from typing import TypeVar, Generic, Set, Type, Dict, Any, Callable

from ..nodes import Node, NodeFactory, ResetException, FatalException

from ...llm import MessageHistory, ModelBase, SystemMessage, Tool, ToolCall, ToolResponse, ToolMessage

from abc import ABC, abstractmethod


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
        self.message_hist = message_history

    @abstractmethod
    def connected_nodes(self) -> Set[Type[Node] | Callable]: ...

    def create_node(self, tool_name: str, arguments: Dict[str, Any]) -> Node:
        """
        A function which creates a new instance of a node from a tool name and arguments.

        This function may be overwritten to fit the needs of the given node as needed.
        """
        node = [x for x in self.connected_nodes() if x.tool_info().name == tool_name]
        if node is []:
            raise ResetException(node=self, detail=f"Tool {tool_name} cannot be create a node")
        if len(node) > 1:
            raise FatalException(
                node=self,
                detail=f"Tool {tool_name} has multiple nodes, this is not allowed. Current Node include {[x.tool_info().name for x in self.connected_nodes()]}",
            )
        return node[0].prepare_tool(arguments)

    def tools(self):
        return [x.tool_info() for x in self.connected_nodes()]

    @abstractmethod
    def return_output(self) -> _T: ...

    def invoke(
        self,
    ) -> _T:
        while True:
            # collect the response from the model
            try:
                returned_mess = self.model.chat_with_tools(self.message_hist, tools=self.tools())
                self.message_hist.append(returned_mess.message)
            except Exception as e:
                raise ResetException(node=self, detail=f"{e}")

            if returned_mess.message.role == "assistant":
                # if the returned item is a list then it is a list of tool calls
                if isinstance(returned_mess.message.content, list):
                    assert all([isinstance(x, ToolCall) for x in returned_mess.message.content])
                    new_nodes = [
                        NodeFactory(
                            lambda arguments: self.create_node(tool_name=t_c.name, arguments=arguments), t_c.arguments
                        )
                        for t_c in returned_mess.message.content
                    ]

                    responses = self.call_nodes(new_nodes)
                    for r_id, resp in zip(
                        [x.identifier for x in returned_mess.message.content],
                        [x.data for x in responses],
                    ):
                        self.message_hist.append(ToolMessage(ToolResponse(identifier=r_id, result=str(resp))))

                elif returned_mess.message.content is not None:
                    # this means the tool call is finished
                    break
            else:
                # the message is malformed from the model
                raise ResetException(
                    node=self,
                    detail="ModelLLM returned an unexpected message type.",
                )

        return self.return_output()
