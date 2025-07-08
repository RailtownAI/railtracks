import time
from abc import ABC
import json
from typing import (
    List,
    Dict,
    Type,
    Optional,
    Any,
    Generator,
    Union,
    Set,
    TypeVar,
    Callable,
    Tuple,
)
from pydantic import BaseModel, ValidationError
from ...exceptions.errors import LLMError, NodeInvocationError
import litellm
from litellm.utils import ModelResponse, CustomStreamWrapper

from ..model import ModelBase
from ..message import Message
from ..response import Response, MessageInfo
from ..history import MessageHistory
from ..message import AssistantMessage, ToolMessage
from ..content import ToolCall
from ..tools import Tool, Parameter
import warnings


def _handle_dict_parameters(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Handle the case where parameters are already a dictionary."""
    if "required" not in parameters and "properties" in parameters:
        warnings.warn(
            "The 'required' key is not present in the parameters dictionary. Parsing Properties parameters to check for required fields."
        )
        required: list[str] = []
        for key, value in parameters["properties"].items():
            if value.get("required", True):
                required.append(key)
        parameters["required"] = required
    return parameters


def _handle_set_of_parameters(parameters: Set[Parameter]) -> Dict[str, Any]:
    """Handle the case where parameters are a set of Parameter instances."""
    props: Dict[str, Any] = {}
    required: list[str] = []
    for p in parameters:
        props[p.name] = {
            "type": p.param_type,
            "description": p.description,
        }
        if p.param_type == "object":
            props[p.name]["additionalProperties"] = p.additional_properties
        if p.required:
            required.append(p.name)

    model_schema: Dict[str, Any] = {
        "type": "object",
        "properties": props,
    }
    if required:
        model_schema["required"] = required
    return model_schema


def _parameters_to_json_schema(
    parameters: Union[Type[BaseModel], Set[Parameter], Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Turn one of:
      - a Pydantic model class (subclass of BaseModel)
      - a set of Parameter instances
      - an already-built dict
    into a JSON Schema dict.
    """
    if isinstance(parameters, dict):
        return _handle_dict_parameters(parameters)
    if isinstance(parameters, type) and issubclass(parameters, BaseModel):
        dump = getattr(parameters, "model_json_schema", None)
        if callable(dump):
            return dump()
        raise RuntimeError(f"Cannot get schema from Pydantic model {parameters!r}")
    if isinstance(parameters, set):
        return _handle_set_of_parameters(parameters)

    raise NodeInvocationError(
        message="Unable to parse Tool.parameters. Please check the documentation for Tool.parameters.",
        fatal=True,
        notes=[
            "Tool.parameters must be either:",
            "  • a dict,",
            "  • a subclass of pydantic.BaseModel, or",
            "  • a set of Parameter instances",
        ],
    )


def _to_litellm_tool(tool: Tool) -> Dict[str, Any]:
    """
    Convert your Tool object into the dict format for litellm.completion.
    """
    # parameters may be None
    raw_params = tool.parameters or {}
    json_schema = _parameters_to_json_schema(raw_params)

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.detail,
            "parameters": json_schema,
        },
    }


def _to_litellm_message(msg: Message) -> Dict[str, Any]:
    """
    Convert your Message (UserMessage, AssistantMessage, ToolMessage) into
    the simple dict format that litellm.completion expects.
    """
    base = {"role": msg.role}
    # handle the special case where the message is a tool so we have to link it to the tool id.
    if isinstance(msg, ToolMessage):
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


class LiteLLMWrapper(ModelBase, ABC):
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

    def __init__(self, model_name: str, **kwargs):
        super().__init__(**kwargs)
        self._model_name = model_name
        self._default_kwargs = kwargs

    def _invoke(
        self,
        messages: MessageHistory,
        *,
        stream: bool = False,
        response_format: Optional[Any] = None,
        **call_kwargs: Any,
    ) -> Tuple[Union[ModelResponse, CustomStreamWrapper], MessageInfo]:
        """
        Internal helper that:
          1. Converts MessageHistory
          2. Merges default kwargs
          3. Calls litellm.completion
        """
        start_time = time.time()
        litellm_messages = [_to_litellm_message(m) for m in messages]
        merged = {**self._default_kwargs, **call_kwargs}
        if response_format is not None:
            merged["response_format"] = response_format
        warnings.filterwarnings(
            "ignore", category=UserWarning, module="pydantic.*"
        )  # Supress pydantic warnings. See issue #204 for more deatils.
        completion = litellm.completion(
            model=self._model_name, messages=litellm_messages, stream=stream, **merged
        )
        mess_info = self.extract_message_info(completion, time.time() - start_time)
        return completion, mess_info

    async def _ainvoke(
        self,
        messages: MessageHistory,
        *,
        stream: bool = False,
        response_format: Optional[Any] = None,
        **call_kwargs: Any,
    ) -> Tuple[Union[ModelResponse, CustomStreamWrapper], MessageInfo]:
        """
        Internal helper that:
          1. Converts MessageHistory
          2. Merges default kwargs
          3. Calls litellm.completion
        """
        start_time = time.time()
        litellm_messages = [_to_litellm_message(m) for m in messages]
        merged = {**self._default_kwargs, **call_kwargs}
        if response_format is not None:
            merged["response_format"] = response_format
        warnings.filterwarnings(
            "ignore", category=UserWarning, module="pydantic.*"
        )  # Supress pydantic warnings. See issue #204 for more deatils.
        completion = await litellm.acompletion(
            model=self._model_name, messages=litellm_messages, stream=stream, **merged
        )

        mess_info = self.extract_message_info(completion, time.time() - start_time)

        return completion, mess_info

    def _chat_handle_base(self, raw: ModelResponse, info: MessageInfo):
        content = raw["choices"][0]["message"]["content"]
        return Response(message=AssistantMessage(content=content), message_info=info)

    def _chat(self, messages: MessageHistory, **kwargs) -> Response:
        raw = self._invoke(messages=messages, **kwargs)
        return self._chat_handle_base(*raw)

    async def _achat(self, messages: MessageHistory, **kwargs) -> Response:
        raw = await self._ainvoke(messages=messages, **kwargs)
        return self._chat_handle_base(*raw)

    def _structured_handle_base(
        self,
        raw: ModelResponse,
        info: MessageInfo,
        schema: Type[BaseModel],
    ) -> Response:
        content_str = raw["choices"][0]["message"]["content"]
        parsed = schema(**json.loads(content_str))
        return Response(message=AssistantMessage(content=parsed), message_info=info)

    def _structured(
        self, messages: MessageHistory, schema: Type[BaseModel], **kwargs
    ) -> Response:
        try:
            model_resp, info = self._invoke(messages, response_format=schema, **kwargs)
            return self._structured_handle_base(model_resp, info, schema)
        except ValidationError as ve:
            raise ve
        except Exception as e:
            raise LLMError(
                reason="Structured LLM call failed",
                message_history=messages,
            ) from e

    async def _astructured(
        self, messages: MessageHistory, schema: Type[BaseModel], **kwargs
    ) -> Response:
        try:
            model_resp, info = await self._ainvoke(
                messages, response_format=schema, **kwargs
            )
            return self._structured_handle_base(model_resp, info, schema)
        except Exception as e:
            raise LLMError(
                reason="Structured LLM call failed",
                message_history=messages,
            ) from e

    def _stream_handler_base(self, raw: CustomStreamWrapper) -> Response:
        # TODO implement tracking in here.
        def streamer() -> Generator[str, None, None]:
            for part in raw:
                yield part.choices[0].delta.content or ""

        return Response(message=None, streamer=streamer())

    def _stream_chat(self, messages: MessageHistory, **kwargs) -> Response:
        stream_iter, info = self._invoke(messages, stream=True, **kwargs)

        return self._stream_handler_base(stream_iter)

    async def _astream_chat(self, messages: MessageHistory, **kwargs) -> Response:
        stream_iter, info = await self._ainvoke(messages, stream=True, **kwargs)
        return self._stream_handler_base(stream_iter)

    def _update_kwarg_with_tool(self, tools: List[Tool], **kwargs):
        litellm_tools = [_to_litellm_tool(t) for t in tools]

        kwargs["tools"] = litellm_tools

        return kwargs

    def _chat_with_tools_handler_base(
        self, raw: ModelResponse, info: MessageInfo
    ) -> Response:
        """
        Handle the response from litellm.completion when using tools.
        """
        choice = raw.choices[0]

        if choice.finish_reason == "stop" and not choice.message.tool_calls:
            return Response(message=AssistantMessage(content=choice.message.content))

        calls: List[ToolCall] = []
        for tc in choice.message.tool_calls:
            args = json.loads(tc.function.arguments)
            calls.append(
                ToolCall(identifier=tc.id, name=tc.function.name, arguments=args)
            )

        return Response(message=AssistantMessage(content=calls), message_info=info)

    def _chat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs: Any
    ) -> Response:
        """
        Chat with the model using tools.

        Args:
            messages: The message history to use as context
            tools: The tools to make available to the model
            **kwargs: Additional arguments to pass to litellm.completion

        Returns:
            A Response containing either plain assistant text or ToolCall(s).
        """

        kwargs = self._update_kwarg_with_tool(tools, **kwargs)
        resp, info = self._invoke(messages, **kwargs)
        resp: ModelResponse

        return self._chat_with_tools_handler_base(resp, info)

    async def _achat_with_tools(
        self, messages: MessageHistory, tools: List[Tool], **kwargs
    ) -> Response:
        kwargs = self._update_kwarg_with_tool(tools, **kwargs)

        resp, info = await self._ainvoke(messages, **kwargs)

        return self._chat_with_tools_handler_base(resp, info)

    def __str__(self) -> str:
        parts = self._model_name.split("/", 1)
        if len(parts) == 2:
            return f"LiteLLMWrapper(provider={parts[0]}, name={parts[1]})"
        return f"LiteLLMWrapper(name={self._model_name})"

    def model_name(self) -> str | None:
        """
        Returns the model name.
        """
        return self._model_name

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


def _return_none_on_error(func: Callable[[], _T]) -> _T:
    try:
        return func()
    except:  # noqa: E722
        return None
