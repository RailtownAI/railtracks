import asyncio
import warnings
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generic, ParamSpec, Set, Type, TypeVar, Union

from requestcompletion import context
from requestcompletion.exceptions import LLMError, NodeCreationError
from requestcompletion.exceptions.node_creation.validation import check_connected_nodes
from requestcompletion.exceptions.node_invocation.validation import check_max_tool_calls
from requestcompletion.interaction.call import call
from requestcompletion.llm import (
    AssistantMessage,
    MessageHistory,
    ModelBase,
    ToolCall,
    ToolMessage,
    ToolResponse,
    UserMessage,
)

from ...nodes import Node
from .._llm_base import LLMBase

_T = TypeVar("_T")
_P = ParamSpec("_P")


class OutputLessToolCallLLM(LLMBase[_T], ABC, Generic[_T]):
    """A base class that is a node which contains
     an LLm that can make tool calls. The tool calls will be returned
    as calls or if there is a response, the response will be returned as an output"""

    # Set structured response node to None by default
    structured_resp_node = None

    def __init_subclass__(cls):
        super().__init_subclass__()
        # 3. Check if the connected_nodes is not empty, special case for ToolCallLLM
        # We will not check for abstract classes
        has_abstract_methods = any(
            getattr(getattr(cls, name, None), "__isabstractmethod__", False)
            for name in dir(cls)
        )
        if not has_abstract_methods:
            if "connected_nodes" in cls.__dict__ and not has_abstract_methods:
                method = cls.__dict__["connected_nodes"]
                try:
                    # Try to call the method as a classmethod (typical case)
                    node_set = method.__func__(cls)
                except AttributeError:
                    # If that fails, call it as an instance method (for easy_wrapper init)
                    dummy = object.__new__(cls)
                    node_set = method(dummy)
                # Validate that the returned node_set is correct and contains only Node/function instances
                check_connected_nodes(node_set, Node)

    def __init__(
        self,
        message_history: MessageHistory,
        llm_model: ModelBase | None = None,
        max_tool_calls: int | None = None,
    ):
        super().__init__(llm_model=llm_model, message_history=message_history)
        # Set max_tool_calls for non easy usage wrappers
        if not hasattr(self, "max_tool_calls"):
            # Check if max_tool_calls was passed
            if max_tool_calls is not None:
                check_max_tool_calls(max_tool_calls)
                self.max_tool_calls = max_tool_calls
            # Default to unlimited if not passed
            else:
                self.max_tool_calls = None

        # Warn user that two max_tool_calls are set and we will use the parameter
        else:
            if max_tool_calls is not None:
                warnings.warn(
                    "You have provided max_tool_calls as a parameter and as a class variable. We will use the parameter."
                )
                check_max_tool_calls(max_tool_calls)
                self.max_tool_calls = max_tool_calls
            else:
                check_max_tool_calls(self.max_tool_calls)

    @classmethod
    def pretty_name(cls) -> str:
        return (
            "ToolCallLLM("
            + ", ".join([x.pretty_name() for x in cls.connected_nodes()])
            + ")"
        )

    @classmethod
    @abstractmethod
    def connected_nodes(cls) -> Set[Union[Type[Node], Callable]]: ...

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
        returned_mess = await self.llm_model.achat_with_tools(
            self.message_hist, tools=[]
        )
        self.message_hist.append(returned_mess.message)

    async def _handle_tool_calls(self):
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

            # collect the response from the llm model
            returned_mess = await self.llm_model.achat_with_tools(
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
                # the message is malformed from the llm model
                raise LLMError(
                    reason="ModelLLM returned an unexpected message type.",
                    message_history=self.message_hist,
                )

    async def invoke(self) -> _T:
        await self._handle_tool_calls()

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

        if (key := self.return_into()) is not None:
            output = self.return_output()
            context.put(key, self.format_for_context(output))
            return self.format_for_return(output)

        return self.return_output()
