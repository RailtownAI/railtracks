import asyncio
import warnings
from copy import deepcopy
from typing import Set, Type, Union, Literal, Dict, Any, Callable, TypeVar, Generic
from pydantic import BaseModel
from inspect import isclass, isfunction
from abc import ABC, abstractmethod
from requestcompletion.llm import (
    MessageHistory,
    SystemMessage,
    ModelBase,
    ToolCall,
    ToolResponse,
    ToolMessage,
    UserMessage,
    AssistantMessage,
)
from requestcompletion.nodes.library import structured_llm
from requestcompletion.nodes.library.function import from_function
from requestcompletion.run import call
from requestcompletion.nodes.library.easy_usage_wrappers.easy_base import EasyBase
from requestcompletion.nodes.nodes import Node
from requestcompletion.exceptions import NodeCreationError, LLMError
from requestcompletion.exceptions.node_invocation.validation import check_max_tool_calls
from requestcompletion.exceptions import NodeCreationError
from requestcompletion.exceptions.node_invocation.validation import check_model
import requestcompletion as rc

_T = TypeVar("_T")


class ToolCallBase(EasyBase[_T], ABC, Generic[_T]):
    def __init_subclass__(
        cls,
        output_type: Literal["MessageHistory", "LastMessage"] = "LastMessage",
        output_model: BaseModel | None = None,
        connected_nodes = Set[Union[Type[Node], Callable]],
        **kwargs,
    ):
        has_abstract_methods = any(
        getattr(getattr(cls, name, None), '__isabstractmethod__', False)
        for name in dir(cls)
        )

        if not has_abstract_methods:
            # If a function is passed in, we will convert it to a node
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
                else:
                    raise NodeCreationError(
                        message=f"Tools must be of type Node or FunctionType but got {type(elem)}",
                        notes=[
                            "Please make sure you are passing in a function or a Node object to connected_nodes"
                        ],
                    )

            # Initialize class wide variables passed by factory function
            cls._connected_nodes = connected_nodes
            cls._output_type = output_type
            cls._output_model = output_model

        # Now that attributes are set, we can validate the attributes
        super().__init_subclass__(**kwargs)

    def __init__(
        self,
        message_history: MessageHistory,
        llm_model: ModelBase | None = None,
        max_tool_calls: int | None = 30,
    ):
        
        if llm_model is not None:
            if self.__class__._model is not None:
                warnings.warn(
                    "You have provided a model as a parameter and as a class variable. We will use the parameter."
                )
        else:
            check_model(
                self.__class__._model
            )  # raises NodeInvocationError if any of the checks fail
            llm_model = self.__class__._model

        super().__init__(message_history=message_history, llm_model=llm_model)
        check_max_tool_calls(max_tool_calls)
        self.structured_resp_node = None  # The structured LLM node
        self.max_tool_calls = max_tool_calls

        if self.__class__._output_model:
            system_structured = SystemMessage(
                "You are a structured LLM that can convert the response into a structured output."
            )
            self.structured_resp_node = structured_llm(
                self.__class__._output_model,
                system_message=system_structured,
                model=llm_model,
            )

    @abstractmethod
    def connected_nodes(self) -> Set[Union[Type[Node], Callable]]: ...

    @classmethod
    def pretty_name(cls) -> str:
        if cls._pretty_name is None:
            return (
                "ToolCallLLM("
                + ", ".join([x.pretty_name() for x in cls._connected_nodes])
                + ")"
            )
        else:
            return cls._pretty_name
    
    
    async def _on_max_tool_calls_exceeded(self):
        """force a final response"""
        returned_mess = self.model.chat_with_tools(self.message_hist, tools=[])
        self.message_hist.append(returned_mess.message)

    def return_output(self):
        if self.__class__._output_model:
            if isinstance(self.structured_output, Exception):
                raise self.structured_output
            return self.structured_output
        elif self.__class__._output_type == "MessageHistory":
            return self.message_hist
        else:
            return self.message_hist[-1]
        
    def tools(self):
        return [x.tool_info() for x in self.connected_nodes()]
        
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
            returned_mess = self.model.chat_with_tools(
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
