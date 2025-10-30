from __future__ import annotations

import json
import time
import warnings
from abc import ABC
from json import JSONDecodeError
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    TypeVar,
    overload,
)

import litellm
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import ModelResponse
from pydantic import BaseModel, Field

from ...exceptions.errors import LLMError, NodeInvocationError
from ..content import ToolCall
from ..history import MessageHistory
from ..message import AssistantMessage, Message, ToolMessage, UserMessage
from ..model import ModelBase
from ..response import MessageInfo, Response
from ..tools import Tool
from ..tools.parameters import Parameter

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)


def _process_single_parameter(p: Parameter) -> tuple[str, Dict[str, Any], bool]:
    """
    Process a single parameter and return (name, prop_dict, is_required).
    We now just defer entirely to each Parameter instance's .to_json_schema() method.
    """
    prop_dict = p.to_json_schema()
    return p.name, prop_dict, p.required


def _handle_set_of_parameters(
    parameters: List[Parameter],
    sub_property: bool = False,
) -> Dict[str, Any]:
    """
    Handle a set of Parameter instances and convert to JSON schema.
    If sub_property is True, returns just the properties dict, else return full schema.
    """
    props: Dict[str, Any] = {}
    required: list[str] = []

    for p in parameters:
        name, prop_dict, is_required = _process_single_parameter(p)
        props[name] = prop_dict
        if is_required:
            required.append(name)

    if sub_property:
        return props
    else:
        schema = {
            "type": "object",
            "properties": props,
        }
        if required:
            schema["required"] = required
        return schema


def _parameters_to_json_schema(
    parameters: List[Parameter] | None,
) -> Dict[str, Any]:
    """
    Turn a set of Parameter instances
    into a JSON Schema dict accepted by litellm.completion.
    """
    if parameters is None:
        return {}

    if isinstance(parameters, Iterable) and all(
        isinstance(x, Parameter) for x in parameters
    ):
        return _handle_set_of_parameters(list(parameters))

    raise NodeInvocationError(
        message=f"Unable to parse Tool.parameters. It was {parameters}",
        fatal=True,
        notes=[
            "Tool.parameters must be a set of Parameter objects",
        ],
    )


def _to_litellm_tool(tool: Tool) -> Dict[str, Any]:
    """
    Convert your Tool object into the dict format for litellm.completion.
    """
    # parameters may be None
    json_schema = _parameters_to_json_schema(tool.parameters)
    litellm_tool = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.detail,
            "parameters": json_schema,
        },
    }
    return litellm_tool


class StreamedToolCall(BaseModel):
    tool: ToolCall
    args: str | None = Field(default=None)  # accumulating string of arguments (in json)

    def load_args(self):
        try:
            self.tool.arguments = json.loads(self.args) if self.args else {}
        except JSONDecodeError as e:
            raise ValueError(
                f"Failed to decode tool call arguments: {str(e)}",
            )


_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class LiteLLMWrapper(ModelBase[_TStream], ABC, Generic[_TStream]):
    """
    A large base class that wraps around a litellm model.

    Note that the model object should be interacted with via the methods provided in the wrapper class:
    - `chat`
    - `structured`
    - `stream_chat`
    - `chat_with_tools`

    Each individual API should implement the required `abstract_methods` in order to allow users to interact with a
    model of that type.
    """

    def __init__(
        self,
        model_name: str,
        stream: _TStream = False,
        api_base: str | None = None,
        api_key: str | None = None,
    ):
        super().__init__(stream=stream)
        self._model_name = model_name
        self.api_base = api_base
        self.api_key = api_key

    @overload
    def _invoke(
        self: LiteLLMWrapper[Literal[False]],
        messages: MessageHistory,
        *,
        response_format: Optional[Any] = None,
        tools: Optional[list[Tool]] = None,
    ) -> Tuple[ModelResponse, float]:
        pass

    @overload
    def _invoke(
        self: LiteLLMWrapper[Literal[True]],
        messages: MessageHistory,
        *,
        response_format: Optional[Any] = None,
        tools: Optional[list[Tool]] = None,
    ) -> Tuple[CustomStreamWrapper, float]:
        pass

    def _invoke(
        self,
        messages: MessageHistory,
        *,
        response_format: Optional[Any] = None,
        tools: Optional[list[Tool]] = None,
    ) -> Tuple[CustomStreamWrapper | ModelResponse, float]:
        """
        Internal helper that:
          1. Converts MessageHistory
          2. Merges default kwargs
          3. Calls litellm.completion
        """
        start_time = time.time()
        litellm_messages = [self._to_litellm_message(m) for m in messages]
        merged = {}

        if response_format is not None:
            merged["response_format"] = response_format

        if tools is not None:
            litellm_tools = [_to_litellm_tool(t) for t in tools]
            merged["tools"] = litellm_tools

        if self.api_base is not None:
            merged["api_base"] = self.api_base

        if self.api_key is not None:
            merged["api_key"] = self.api_key

        warnings.filterwarnings(
            "ignore", category=UserWarning, module="pydantic.*"
        )  # Supress pydantic warnings. See issue #204 for more deatils.

        completion = litellm.completion(
            model=self._model_name,
            messages=litellm_messages,
            stream=self.stream,
            **merged,
        )

        if isinstance(completion, CustomStreamWrapper):
            return completion, start_time
        else:
            completion_time = time.time() - start_time
            return completion, completion_time

    @overload
    async def _ainvoke(
        self: LiteLLMWrapper[Literal[False]],
        messages: MessageHistory,
        *,
        response_format: Any | None = None,
        tools: Optional[list[Tool]] = None,
    ) -> Tuple[ModelResponse, float]:
        pass

    @overload
    async def _ainvoke(
        self: LiteLLMWrapper[Literal[True]],
        messages: MessageHistory,
        *,
        response_format: Any | None = None,
        tools: Optional[list[Tool]] = None,
    ) -> Tuple[CustomStreamWrapper, float]:
        pass

    async def _ainvoke(
        self,
        messages: MessageHistory,
        *,
        response_format: Optional[Any] = None,
        tools: Optional[list[Tool]] = None,
    ) -> Tuple[CustomStreamWrapper | ModelResponse, float]:
        """
        Internal helper that:
          1. Converts MessageHistory
          2. Merges default kwargs
          3. Calls litellm.completion
        """
        start_time = time.time()
        litellm_messages = [self._to_litellm_message(m) for m in messages]
        merged = {}
        if response_format is not None:
            merged["response_format"] = response_format
        if tools is not None:
            litellm_tools = [_to_litellm_tool(t) for t in tools]
            merged["tools"] = litellm_tools
        warnings.filterwarnings(
            "ignore", category=UserWarning, module="pydantic.*"
        )  # Supress pydantic warnings. See issue #204 for more deatils.
        completion = await litellm.acompletion(
            model=self._model_name,
            messages=litellm_messages,
            stream=self.stream,
            **merged,
        )
        if isinstance(completion, CustomStreamWrapper):
            return completion, start_time
        else:
            completion_time = time.time() - start_time
            return completion, completion_time

    # ================ START Streaming Handlers ===============
    async def _astream_handler_base(
        self,
        raw: CustomStreamWrapper,
        start_time: float,
        output_schema: Type[BaseModel] | None = None,
    ):
        """
        Add handler to the streamed response so that we preoperly construct the response object at the end of the stream.
        """
        tools: List[ToolCall] = []
        accumulated_content = ""
        structured_response: BaseModel | None = None
        # fall back on empty message info if we don't get one from the stream.
        message_info = MessageInfo()
        active_tool_calls: Dict[int, StreamedToolCall] = {}
        stream_finished = False

        async for chunk in raw.completion_stream:
            if stream_finished:
                # the last chunk will contain the full message info
                message_info = self.extract_message_info(
                    chunk, time.time() - start_time
                )

                if output_schema is not None:
                    structured_response = output_schema(
                        **json.loads(accumulated_content)
                    )
                break

            choice = chunk.choices[0]

            if self._is_stream_finished(choice):
                stream_finished = True
                tools = self._finalize_remaining_tool_calls(active_tool_calls)
                continue

            if choice.delta.tool_calls:
                # TODO: determine if it would be useful to stream tools
                self._handle_tool_call_delta(
                    choice.delta.tool_calls[0], active_tool_calls
                )

            elif choice.delta.content:
                content = self._handle_content_delta(choice.delta.content)
                accumulated_content += content
                yield content

        if structured_response is not None:
            r = Response(
                message=AssistantMessage(content=structured_response),
                message_info=message_info,
            )
        elif len(tools) > 0:
            r = Response(
                message=AssistantMessage(content=tools), message_info=message_info
            )
        else:
            r = Response(
                message=AssistantMessage(content=accumulated_content),
                message_info=message_info,
            )

        yield r

    def _stream_handler_base(
        self,
        raw: CustomStreamWrapper,
        start_time: float,
        output_schema: Type[_TBaseModel] | None = None,
    ) -> Generator[Response | str, None, Response]:
        """
        Intercepts the given stream wrapper and provides a new generator.
        The generator should iterate and provide strings cluminating in the last response being a Response object

        """
        tools: List[ToolCall] = []
        accumulated_content = ""

        # fall back on empty message info if we don't get one from the stream.
        message_info = MessageInfo()
        active_tool_calls: Dict[int, StreamedToolCall] = {}
        stream_finished = False

        for chunk in raw:
            if stream_finished:
                # the last chunk will contain the full message info. Note this only true for openai. Anthropic is known to not.

                message_info = self.extract_message_info(
                    chunk, time.time() - start_time
                )

                break

            choice = chunk.choices[0]

            if self._is_stream_finished(choice):
                stream_finished = True
                tools = self._finalize_remaining_tool_calls(active_tool_calls)
                continue

            if choice.delta.tool_calls:
                self._handle_tool_call_delta(
                    choice.delta.tool_calls[0], active_tool_calls
                )

            elif choice.delta.content:
                content = self._handle_content_delta(choice.delta.content)
                accumulated_content += content
                yield content

        r = self._prepare_response(
            accumulated_content=accumulated_content,
            tools=tools,
            output_schema=output_schema,
            message_info=message_info,
        )

        yield r
        return r

    def _prepare_response(
        self,
        *,
        accumulated_content: str,
        tools: list[ToolCall],
        output_schema: type[BaseModel] | None,
        message_info: MessageInfo,
    ):
        """
        From the provided content, creates a completes a response object dyanmically.

        This function handles the normalization of the different response `content` types.
        """
        structured_response: BaseModel | None = None

        if output_schema is not None:
            structured_response = output_schema(**json.loads(accumulated_content))

        if structured_response is not None:
            r = Response(
                message=AssistantMessage(content=structured_response),
                message_info=message_info,
            )
        elif len(tools) > 0:
            r = Response(
                message=AssistantMessage(content=tools), message_info=message_info
            )
        else:
            r = Response(
                message=AssistantMessage(content=accumulated_content),
                message_info=message_info,
            )

        return r

    async def _aconsume_stream(self, raw: CustomStreamWrapper, start_time: float):
        """Consume the entire async stream and extract chunks, content, and metadata."""
        return self._stream_handler_base(raw, start_time)

    def _is_stream_finished(self, choice) -> bool:
        """Check if the stream has finished."""
        return choice.finish_reason in ("stop", "tool_calls")

    def _finalize_remaining_tool_calls(
        self, active_tool_calls: dict[int, StreamedToolCall]
    ) -> list[ToolCall]:
        """

        Finalize any remaining active tool calls and return them.

        """
        tools: list[ToolCall] = []
        for tool_data in active_tool_calls.values():
            if tool_data.args is not None:
                tool_data.load_args()
            tools.append(tool_data.tool)

        return tools

    def _handle_tool_call_delta(
        self, call, active_tool_calls: dict[int, StreamedToolCall]
    ):
        """Process a tool call delta from the stream."""
        call_index = getattr(call, "index", 0)

        if call.id:  # New tool call starting
            self._start_new_tool_call(call, call_index, active_tool_calls)
        else:  # Continue streaming arguments
            self._continue_tool_call_arguments(call, call_index, active_tool_calls)

    def _start_new_tool_call(
        self, call, call_index: int, active_tool_calls: dict[int, StreamedToolCall]
    ):
        """Start a new tool call, finalizing any previous one at the same index."""
        # Finalize previous tool call at this index if exists
        if call_index in active_tool_calls:
            prev_data = active_tool_calls[call_index]
            if prev_data.args:
                prev_data.tool.arguments = json.loads(prev_data.args)

        # Start new tool call
        active_tool_calls[call_index] = StreamedToolCall(
            tool=ToolCall(identifier=call.id, name=call.function.name, arguments={}),
            args="",
        )

    def _continue_tool_call_arguments(
        self, call, call_index: int, active_tool_calls: dict[int, StreamedToolCall]
    ):
        """Continue accumulating arguments for an existing tool call."""
        if call_index in active_tool_calls and call.function.arguments:
            active_tool_calls[call_index].args += call.function.arguments

    def _handle_content_delta(self, content) -> str:
        """Process content delta and return validated content string."""
        assert isinstance(content, str)
        return content or ""

    # ================ END Streaming Handlers ===============

    # ================ START Base Handlers ==================

    def _chat_handle_base(self, raw: ModelResponse, info: MessageInfo):
        content = raw["choices"][0]["message"]["content"]
        return Response(message=AssistantMessage(content=content), message_info=info)

    def _structured_handle_base(
        self,
        raw: ModelResponse,
        info: MessageInfo,
        schema: Type[BaseModel],
    ) -> Response:
        content_str = raw["choices"][0]["message"]["content"]
        parsed = schema(**json.loads(content_str))
        return Response(message=AssistantMessage(content=parsed), message_info=info)

    def _chat_with_tools_handler_base(
        self, raw: ModelResponse, info: MessageInfo
    ) -> Response:
        """
        Handle the response from litellm.completion when using tools.
        """
        choice = raw.choices[0]

        if choice.finish_reason == "stop" and not choice.message.tool_calls:
            return Response(
                message=AssistantMessage(content=choice.message.content),
                message_info=info,
            )

        calls: List[ToolCall] = []
        for tc in choice.message.tool_calls:
            args = json.loads(tc.function.arguments)
            calls.append(
                ToolCall(identifier=tc.id, name=tc.function.name, arguments=args)
            )

        return Response(message=AssistantMessage(content=calls), message_info=info)

    # ================ END Base Handlers ===============

    # ================ START Sync LLM calls ===============

    def _chat(self, messages: MessageHistory):
        response, time = self._invoke(messages=messages)
        if isinstance(response, CustomStreamWrapper):
            return self._stream_handler_base(response, time)

        elif isinstance(response, ModelResponse):
            return self._chat_handle_base(
                response, self.extract_message_info(response, time)
            )
        else:
            raise ValueError("Unexpected response type")

    def _structured(self, messages: MessageHistory, schema: Type[BaseModel]):
        try:
            model_resp, time = self._invoke(messages, response_format=schema)
            if isinstance(model_resp, CustomStreamWrapper):
                return self._stream_handler_base(model_resp, time, schema)
            elif isinstance(model_resp, ModelResponse):
                return self._structured_handle_base(
                    model_resp,
                    self.extract_message_info(model_resp, time),
                    schema,
                )
            else:
                raise ValueError("Unexpected response type")
        except JSONDecodeError as jde:
            raise jde
        except Exception as e:
            raise LLMError(
                reason="Structured LLM call failed",
                message_history=messages,
            ) from e

    def _chat_with_tools(self, messages: MessageHistory, tools: List[Tool]):
        """
        Chat with the model using tools.

        Args:
            messages: The message history to use as context
            tools: The tools to make available to the model
            **kwargs: Additional arguments to pass to litellm.completion

        Returns:
            A Response containing either plain assistant text or ToolCall(s).
        """
        resp, time = self._invoke(messages, tools=tools)
        if isinstance(resp, CustomStreamWrapper):
            return self._stream_handler_base(resp, time)
        elif isinstance(resp, ModelResponse):
            return self._chat_with_tools_handler_base(
                resp, self.extract_message_info(resp, time)
            )
        else:
            raise ValueError("Unexpected response type")

    # ================ END Sync LLM calls ===============

    # ================ START Async LLM calls ===============
    async def _achat(self, messages: MessageHistory):
        response, time = await self._ainvoke(messages=messages)
        if isinstance(response, CustomStreamWrapper):
            return self._astream_handler_base(response, time)
        elif isinstance(response, ModelResponse):
            return self._chat_handle_base(
                response, self.extract_message_info(response, time)
            )
        else:
            raise ValueError("Unexpected response type")

    async def _astructured(self, messages: MessageHistory, schema: Type[BaseModel]):
        try:
            model_resp, time = await self._ainvoke(messages, response_format=schema)
            if isinstance(model_resp, CustomStreamWrapper):
                return self._astream_handler_base(model_resp, time, schema)
            elif isinstance(model_resp, ModelResponse):
                return self._structured_handle_base(
                    model_resp,
                    self.extract_message_info(model_resp, time),
                    schema,
                )
            else:
                raise ValueError("Unexpected response type")
        except JSONDecodeError as jde:
            raise jde
        except Exception as e:
            raise LLMError(
                reason="Structured LLM call failed",
                message_history=messages,
            ) from e

    async def _achat_with_tools(self, messages: MessageHistory, tools: List[Tool]):
        resp, time = await self._ainvoke(messages, tools=tools)
        if isinstance(resp, CustomStreamWrapper):
            return self._astream_handler_base(resp, time)
        elif isinstance(resp, ModelResponse):
            return self._chat_with_tools_handler_base(
                resp, self.extract_message_info(resp, time)
            )
        else:
            raise ValueError("Unexpected response type")

    # ================ END Async LLM calls ===============

    def __str__(self) -> str:
        parts = self._model_name.split("/", 1)
        if len(parts) == 2:
            return f"LiteLLMWrapper(provider={parts[0]}, name={parts[1]})"
        return f"LiteLLMWrapper(name={self._model_name})"

    def model_name(self) -> str:
        """
        Returns the model name.
        """
        return self._model_name

    def _to_litellm_message(self, msg: Message) -> Dict[str, Any]:
        """
        Convert your Message (UserMessage, AssistantMessage, ToolMessage) into
        the simple dict format that litellm.completion expects.
        """
        base: Dict[str, Any] = {"role": msg.role}
        # handle the special case where the message is a tool so we have to link it to the tool id.
        if isinstance(msg, UserMessage) and msg.attachment is not None:
            # Initiate content list with text component
            content_list: List[Dict[str, Any]] = [{"type": "text", "text": msg.content}]

            # Add image attachments
            for msg_attachment in msg.attachment:
                content_list.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": msg_attachment.encoding
                            if msg_attachment.encoding is not None
                            else msg_attachment.url,
                        },
                    }
                )

            base["content"] = content_list

        elif isinstance(msg, ToolMessage):
            base["name"] = msg.content.name
            base["tool_call_id"] = msg.content.identifier
            base["content"] = msg.content.result
        # only time this is true is tool calls, need to return litellm.utils.Message
        elif isinstance(msg.content, list):
            assert all(isinstance(t_c, ToolCall) for t_c in msg.content)
            base["content"] = ""
            base["tool_calls"] = [
                litellm.utils.ChatCompletionMessageToolCall(
                    function=litellm.utils.Function(
                        arguments=tool_call.arguments, name=tool_call.name
                    ),
                    id=tool_call.identifier,
                    type="function",
                )
                for tool_call in msg.content
            ]
        else:
            base["content"] = msg.content
        return base

    @classmethod
    def extract_message_info(
        cls, model_response: ModelResponse, latency: float
    ) -> MessageInfo:
        """
        Create a Response object from a ModelResponse.

        Args:
            model_response (ModelResponse): The response from the model.
            latency (float): The latency of the response in seconds.

        Returns:
            MessageInfo: An object containing the details about the message info.
        """
        input_tokens = _return_none_on_error(lambda: model_response.usage.prompt_tokens)
        output_tokens = _return_none_on_error(
            lambda: model_response.usage.completion_tokens
        )
        model_name = _return_none_on_error(lambda: model_response.model)
        system_fingerprint = _return_none_on_error(
            lambda: model_response.system_fingerprint
        )
        total_cost = _return_none_on_error(
            lambda: model_response._hidden_params["response_cost"]
        )

        return MessageInfo(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency=latency,
            model_name=model_name,
            total_cost=total_cost,
            system_fingerprint=system_fingerprint,
        )


_T = TypeVar("_T")


def _return_none_on_error(func: Callable[[], _T]) -> _T | None:
    try:
        return func()
    except:  # noqa: E722
        return None
