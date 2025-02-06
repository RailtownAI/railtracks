from typing import TypeVar, Generic, Set, Type

from ..nodes import Node, NodeFactory, ResetException

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
    ):
        super().__init__()
        self.model = self.create_model()
        self.message_hist = MessageHistory([SystemMessage(self.system_message())])
        self.message_hist += message_history

    @classmethod
    @abstractmethod
    def system_message(cls) -> str: ...

    @classmethod
    @abstractmethod
    def create_model(cls) -> ModelBase: ...

    # TODO: add functionality to allow for the input of callables here (not just nodes note they should be mapped to nodes on the backend)
    @classmethod
    @abstractmethod
    def tool_details(cls) -> Set[Type[Node]]: ...

    @classmethod
    def tool_name_mapping(cls):
        return {tdn.tool_info().name: tdn.prepare_tool for tdn in cls.tool_details()}

    @classmethod
    def tools(cls):
        return [x.tool_info() for x in cls.tool_details()]

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
                        NodeFactory(self.tool_name_mapping()[t_c.name], t_c.arguments)
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
