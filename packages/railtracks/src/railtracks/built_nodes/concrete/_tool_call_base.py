from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generic,
    Literal,
    ParamSpec,
    Set,
    Type,
    TypeVar,
    cast,
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
from railtracks.llm.providers import TOOL_CALLING_STREAMING_BLACKLIST
from railtracks.llm.response import Response
from railtracks.nodes.nodes import Node
from railtracks.utils.logging import get_rt_logger
from railtracks.validation.node_creation.validation import check_connected_nodes

from ._llm_base import LLMBase

_P = ParamSpec("_P")
_TCollectedOutput = TypeVar("_TCollectedOutput", bound=LLMResponse)

_TContent = TypeVar("_TContent", bound=Content)

logger = get_rt_logger(__name__)


class OutputLessToolCallLLMBase(
    LLMBase[_TCollectedOutput],
    ABC,
    Generic[_TCollectedOutput],
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
        """Providers we do not support token streaming for when tool calling is involved.

        When a streamed invocation hits one of these providers, the node falls back to a
        buffered model call (with a warning) instead of erroring — the final response is
        unaffected, you just don't get incremental chunks.
        """
        return set(TOOL_CALLING_STREAMING_BLACKLIST)

    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
        llm: ModelBase | None = None,
    ):
        super().__init__(llm=llm, user_input=user_input)

    def _should_stream(self) -> bool:
        """Frame-level streaming decision, including the tool-calling provider blacklist."""
        if not super()._should_stream():
            return False
        if self.llm_model.model_provider() in self.streaming_blacklist():
            logger.warning(
                "Streaming is not supported with %s for tool calling; falling back to a "
                "buffered response.",
                self.llm_model.model_provider(),
            )
            return False
        return True

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
        # `prepare_tool` is attached dynamically by the node builder; Node has no static stub.
        return cast(Any, node[0]).prepare_tool(arguments)

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

        # `prepare_tool` is attached dynamically by the node builder; Node has no static stub.
        return await call(cast(Any, node).prepare_tool, **arguments)

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
    OutputLessToolCallLLMBase[_TCollectedOutput],
    ABC,
    Generic[_TCollectedOutput],
):
    async def _handle_tool_calls(
        self,
    ) -> tuple[bool, Message | None, Response | None]:
        """
        Handles the execution of tool calls for the node, including LLM interaction and message history updates.

        This method:
        - Interacts with the LLM to get a tool call request or final answers.
        - Executes a tool call and appends the results to the message history.
        - Handles malformed LLM responses and raises errors as needed.

        Streaming: when the frame has streaming enabled, every round of the tool-call loop is
        requested as a streamed model call and all text chunks are broadcast as they arrive —
        including text produced in rounds that end in tool calls. The returned `Response` is
        always the complete (accumulated) one, so the loop logic is identical either way.

        Returns:
            A 3-tuple ``(still_looping, final_message, final_response)``.
            ``still_looping`` is True when tool calls were dispatched and the
            caller should loop again, False when the LLM produced a final text
            reply.  ``final_message`` and ``final_response`` are non-None only
            when ``still_looping`` is False.

        Raises:
            LLMError: If the LLM returns an unexpected message type or the message is malformed.
        """
        try:
            if self._should_stream():
                response = await self._stream_model_response(
                    self.llm_model.astream_chat_with_tools(
                        self.message_hist, tools=self.tools()
                    )
                )
            else:
                response = await asyncio.to_thread(self._buffered_chat_with_tools)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(
                reason=f"Exception during llm model chat: {repr(e)}",
                message_history=self.message_hist,
            ) from e

        if not response.message.role == Role.assistant:
            raise LLMError(
                reason=f"The LLM returned an unexpected message type. Expected AssistantMessage but got {type(response.message)}",
                message_history=self.message_hist,
            )

        is_tool, message = await self._handle_response(response.message)
        final_response = None if is_tool else response
        return is_tool, message, final_response

    def _buffered_chat_with_tools(self) -> Response:
        """Runs a regular (non-streaming) tool call, draining legacy stream=True generators."""
        return self._collect_streamed_response(
            self.llm_model.chat_with_tools(self.message_hist, tools=self.tools())
        )

    async def invoke(self):
        context = self._pre_invoke(self.message_hist)
        self.message_hist = context

        message = None
        final_response = None
        while True:
            still_tool_calls, message, final_response = await self._handle_tool_calls()
            if not still_tool_calls:
                break

        if final_response is not None:
            guarded = self._post_invoke(self.message_hist, final_response)
            if isinstance(guarded, Response) and guarded is not final_response:
                message = guarded.message
                self.message_hist[-1] = message

        return self.return_output(message)
