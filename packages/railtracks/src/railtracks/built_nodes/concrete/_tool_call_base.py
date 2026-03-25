from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generator,
    Generic,
    Literal,
    ParamSpec,
    Set,
    Type,
    TypeVar,
)

from railtracks.built_nodes.concrete.response import LLMResponse
from railtracks.exceptions import LLMError, NodeCreationError
from railtracks.interaction._call import call
from railtracks.llm import (
    AssistantMessage,
    Message,
    MessageHistory,
    ModelBase,
    ToolCall,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from railtracks.llm.content import Content
from railtracks.llm.message import Role
from railtracks.llm.providers import ModelProvider
from railtracks.llm.response import Response
from railtracks.nodes.nodes import Node
from railtracks.validation.node_creation.validation import check_connected_nodes

from ._llm_base import LLMBase

_T = TypeVar("_T")
_P = ParamSpec("_P")
_TStream = TypeVar("_TStream", Literal[True], Literal[False])
_TCollectedOutput = TypeVar("_TCollectedOutput", bound=LLMResponse)

_TContent = TypeVar("_TContent", bound=Content)


class OutputLessToolCallLLMBase(
    LLMBase[_T, _TCollectedOutput, _TStream],
    ABC,
    Generic[_T, _TCollectedOutput, _TStream],
):
    """A base class that is a node which contains
     an LLm that can make tool calls. The tool calls will be returned
    as calls or if there is a response, the response will be returned as an output"""

    def __init_subclass__(cls):
        super().__init_subclass__()
        # 3. Check if the tool_nodes is not empty, special case for ToolCallLLM
        # We will not check for abstract classes
        has_abstract_methods = any(
            getattr(getattr(cls, name, None), "__isabstractmethod__", False)
            for name in dir(cls)
        )
        if not has_abstract_methods:
            if "tool_nodes" in cls.__dict__ and not has_abstract_methods:
                method = cls.__dict__["tool_nodes"]
                try:
                    # Try to call the method as a classmethod (typical case)
                    node_set = method.__func__(cls)
                except AttributeError:
                    # If that fails, call it as an instance method (for easy_wrapper init)
                    dummy = object.__new__(cls)
                    node_set = method(dummy)
                # Validate that the returned node_set is correct and contains only Node/function instances
                check_connected_nodes(node_set, Node)

    @classmethod
    def streaming_blacklist(cls):
        return {
            ModelProvider.ANTHROPIC,
            ModelProvider.AZUREAI,
            ModelProvider.GEMINI,
            ModelProvider.OLLAMA,
            ModelProvider.HUGGINGFACE,
        }

    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
        llm: ModelBase[_TStream] | None = None,
    ):
        super().__init__(llm=llm, user_input=user_input)
        model = self.get_llm()
        # we only support Openai for streaming calls atm.
        if (
            model is not None
            and model.stream
            and model.model_provider() in self.streaming_blacklist()
        ):
            raise NodeCreationError(
                f"Currently we do not allow streaming with {model.model_provider()} (specifically for tool calling)",
                notes=[
                    "Create a new issue on the railtracks repo or switch to openai's models"
                ],
            )

    @classmethod
    def name(cls) -> str:
        return "Tool Call LLM"

    @classmethod
    @abstractmethod
    def tool_nodes(cls) -> Set[Type[Node]]: ...

    def create_node(self, tool_name: str, arguments: Dict[str, Any]) -> Node:
        """
        A function which creates a new instance of a node Class from a tool name and arguments.

        This function may be overwritten to fit the needs of the given node as needed.
        """
        node = [x for x in self.tool_nodes() if x.tool_info().name == tool_name]
        if node == []:
            raise LLMError(
                reason=f" Error creating a node from tool {tool_name}. The tool_name given by the LLM doesn't match any of the tool names in the connected nodes.",
                message_history=self.message_hist,
            )
        if len(node) > 1:
            raise NodeCreationError(
                message=f"Tool {tool_name} has multiple nodes, this is not allowed. Current Node include {[x.tool_info().name for x in self.tool_nodes()]}",
                notes=["Please check the tool names in the connected nodes."],
            )
        return node[0].prepare_tool(arguments)

    def get_node_from_name(self, tool_name: str):
        """
        Gets the node attached to the node of the given name. If no node exists or there are multiple matches, it will raise an exception.
        """
        node = [x for x in self.tool_nodes() if x.tool_info().name == tool_name]
        if node == []:
            raise LLMError(
                reason=f"Error creating a node from tool {tool_name}. The tool_name given by the LLM doesn't match any of the tool names in the connected nodes.",
                message_history=self.message_hist,
            )
        if len(node) > 1:
            raise NodeCreationError(
                message=f"Tool {tool_name} has multiple nodes, this is not allowed. Current Node include {[x.tool_info().name for x in self.tool_nodes()]}",
                notes=["Please check the tool names in the connected nodes."],
            )

        return node[0]

    async def run_node_from_tool(self, tool_name: str, arguments: dict[str, Any]):
        node = self.get_node_from_name(tool_name)

        return await call(node.prepare_tool, **arguments)

    @classmethod
    def tools(cls):
        return [x.tool_info() for x in cls.tool_nodes()]

    async def _call_tools(self, tool_calls: list[ToolCall]) -> list[ToolMessage]:
        contracts = []

        for t_c in tool_calls:
            contract = self.run_node_from_tool(t_c.name, t_c.arguments)
            contracts.append(contract)

        tool_responses = await asyncio.gather(*contracts, return_exceptions=True)
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

        tool_messages = []

        for r_id, r_name, resp in zip(
            tool_ids,
            tool_names,
            tool_responses,
        ):
            tool_messages.append(
                ToolMessage(
                    ToolResponse(identifier=r_id, result=str(resp), name=r_name)
                )
            )

        return tool_messages

    async def _handle_response(
        self,
        message: Message[_TContent, Literal[Role.assistant]],
    ):
        # if the returned item is a list then it is a list of tool calls
        if isinstance(message.content, list):
            assert all(isinstance(x, ToolCall) for x in message.content)

            tool_calls = message.content

            hist_msg = AssistantMessage(
                content=tool_calls
            )  # Preserve provider-specific metadata from the original message

            raw = getattr(message, "raw_litellm_message", None)
            if raw is not None:
                hist_msg.raw_litellm_message = raw
            self.message_hist.append(hist_msg)

            tool_messages = await self._call_tools(tool_calls)
            for t_m in tool_messages:
                self.message_hist.append(t_m)

            return True, None
        else:
            # this means the tool call is finished
            self.message_hist.append(message)
            return False, message


class OutputLessToolCallLLM(
    OutputLessToolCallLLMBase[_TCollectedOutput, _TCollectedOutput, Literal[False]],
    ABC,
    Generic[_TCollectedOutput],
):
    async def _handle_tool_calls(self) -> tuple[bool, Message | None]:
        """
        Handles the execution of tool calls for the node, including LLM interaction and message history updates.

        This method:
        - Interacts with the LLM to get a tool call request or final answers.
        - Executes a tool call and appends the results to the message history.
        - Handles malformed LLM responses and raises errors as needed.

        Returns:
            bool: True if more tool calls are expected (the tool call loop should continue),
                  False if the tool call process is finished and a final answer is available.

        Raises:
            LLMError: If the LLM returns an unexpected message type or the message is malformed.
        """

        # collect the response from the llm model
        response = await asyncio.to_thread(
            self.llm_model.chat_with_tools, self.message_hist, tools=self.tools()
        )

        if not response.message.role == Role.assistant:
            raise LLMError(
                reason=f"The LLM returned an unexpected message type. Expected AssistantMessage but got {type(response.message)}",
                message_history=self.message_hist,
            )

        return await self._handle_response(response.message)

    async def invoke(self):
        message = None
        while True:
            still_tool_calls, message = await self._handle_tool_calls()
            if not still_tool_calls:
                break

        return self.return_output(message)


class StreamingOutputLessToolCallLLM(
    OutputLessToolCallLLMBase[
        Generator[str | _TCollectedOutput, None, _TCollectedOutput],
        _TCollectedOutput,
        Literal[True],
    ],
    ABC,
    Generic[_TCollectedOutput],
):
    async def _handle_tool_calls(self):
        returned_mess = await asyncio.to_thread(
            self.llm_model.chat_with_tools, self.message_hist, tools=self.tools()
        )

        first_item = next(returned_mess)
        if isinstance(first_item, str):

            def gen_wrapper():
                yield first_item
                # yield the rest of the items
                for chunk in returned_mess:
                    if isinstance(chunk, str):
                        yield chunk
                    elif isinstance(chunk, Response):
                        if chunk.message.role != Role.assistant:
                            raise LLMError(
                                reason="ModelLLM returned an unexpected message type.",
                                message_history=self.message_hist,
                            )
                        self.message_hist.append(chunk.message)
                        response = self.return_output(chunk.message)
                        yield response
                        return response

                raise LLMError(
                    "Badly formatted response from the LLM",
                    message_history=self.message_hist,
                )

            return gen_wrapper()

        if isinstance(first_item, Response):
            assert first_item.message.role == Role.assistant

            if len(first_item.message.tool_calls) > 0:
                is_tool, _ = await self._handle_response(
                    first_item.message
                )

                if not is_tool:
                    raise LLMError(
                        "Message returned did not contain tool calls and it should have.",
                        message_history=self.message_hist,
                    )
            else:
                raise LLMError(
                    "Message returned did not contain tool calls and it should have.",
                    message_history=self.message_hist,
                )

    async def invoke(self):
        """Makes a call containing the inputted message and system prompt to the llm model and returns the response
        Returns:
            (TerminalLLM.Output): The response message from the llm model
        """

        while True:
            result = await self._handle_tool_calls()
            if result is not None:
                return result
