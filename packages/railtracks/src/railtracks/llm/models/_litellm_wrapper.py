import json
import time
import warnings
from abc import ABC
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import litellm
from litellm.utils import CustomStreamWrapper, ModelResponse
from pydantic import BaseModel, ValidationError

from ...exceptions.errors import LLMError, NodeInvocationError
from ..content import ToolCall
from ..history import MessageHistory
from ..message import AssistantMessage, Message, ToolMessage
from ..model import ModelBase
from ..response import MessageInfo, Response
from ..tools import ArrayParameter, Parameter, PydanticParameter, Tool


# ================ START Parameter to JSON Schema parsing ===============
# TODO: when we come back to refactor this, move all this logic to a separate file under ../tools
def _create_base_prop_dict(p: "Parameter") -> Dict[str, Any]:
    """Create base property dictionary with type and description."""
    prop_dict = {
        "type": p.param_type,
    }

    if p.description:
        prop_dict["description"] = p.description

    return prop_dict


def _handle_array_type(prop_dict: Dict[str, Any], p: "Parameter") -> None:
    """Handle array type parameters."""
    element_type = (
        p.default or "string"
    )  # Default to 'string' if no element type is provided
    prop_dict["items"] = {"type": element_type}


def _handle_object_type(prop_dict: Dict[str, Any], p: "Parameter") -> None:
    """Handle object type parameters."""
    if (
        isinstance(p, PydanticParameter) and p.ref_path
    ):  # special case for $ref: we only need description and $ref
        prop_dict["$ref"] = p.ref_path
        prop_dict.pop("type")
    else:
        prop_dict["additionalProperties"] = p.additional_properties
        inner_props = getattr(
            p, "properties", set()
        )  # incase props are not present in the schema
        prop_dict["properties"] = _handle_set_of_parameters(inner_props, True)
        sub_required_params = [p.name for p in inner_props if p.required]
        if sub_required_params:
            prop_dict["required"] = sub_required_params


def _handle_union_type(prop_dict: Dict[str, Any], p: "Parameter") -> None:
    """Handle union/list type parameters."""
    any_of_list = []
    for t in p.param_type:
        t = (
            "null" if t == "none" else t
        )  # none can only be found as a type for union/optional and we will convert it to null
        type_item = {"type": t}
        if t == "object":  # override type_item if object
            inner_props = getattr(
                p, "properties", set()
            )  # incase props are not present in the schema
            type_item["properties"] = _handle_set_of_parameters(inner_props, True)
            type_item["description"] = p.description
            type_item["additionalProperties"] = p.additional_properties
        any_of_list.append(type_item)
    prop_dict["anyOf"] = any_of_list
    prop_dict.pop("type")


def _handle_array_parameter(
    p: "ArrayParameter", prop_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle ArrayParameter instances with special array wrapping."""
    items_schema = {"type": "array"}
    if p.description:
        items_schema["description"] = p.description
        prop_dict.pop("description")
    items_schema["items"] = prop_dict
    if p.max_items:
        items_schema["maxItems"] = p.max_items
    return items_schema


def _set_parameter_defaults(prop_dict: Dict[str, Any], p: "Parameter") -> None:
    """Set default values and enum for parameters."""
    if (
        p.default is not None
    ):  # default can be 0 or False, if default value is supposed to be None, the param will be treated as optional
        prop_dict["default"] = p.default
    elif (
        isinstance(p.param_type, list) and "none" in p.param_type
    ):  # if param_type is list and none is in it, the param is optional and default is None
        prop_dict["default"] = None

    if p.enum:
        prop_dict["enum"] = p.enum


def _process_single_parameter(p: "Parameter") -> tuple[str, Dict[str, Any], bool]:
    """Process a single parameter and return (name, prop_dict, is_required)."""
    prop_dict = _create_base_prop_dict(p)

    # Handle different parameter types
    if p.param_type == "array":
        _handle_array_type(prop_dict, p)

    if p.param_type == "object":
        _handle_object_type(prop_dict, p)

    if isinstance(p.param_type, list):
        _handle_union_type(prop_dict, p)

    # Handle ArrayParameter wrapper
    if isinstance(p, ArrayParameter):
        prop_dict = _handle_array_parameter(p, prop_dict)

    # Set defaults and enum
    _set_parameter_defaults(prop_dict, p)

    return p.name, prop_dict, p.required


def _build_final_schema(
    props: Dict[str, Any], required: list[str], sub_property: bool
) -> Dict[str, Any]:
    """Build the final output_schema dictionary."""
    if sub_property:
        return props
    else:
        model_schema: Dict[str, Any] = {
            "type": "object",
            "properties": props,
        }
        if required:
            model_schema["required"] = required
        return model_schema


def _handle_set_of_parameters(
    parameters: List[Parameter | PydanticParameter | ArrayParameter],
    sub_property: bool = False,
) -> Dict[str, Any]:
    """Handle the case where parameters are a set of Parameter instances."""
    props: Dict[str, Any] = {}
    required: list[str] = []

    for p in parameters:
        name, prop_dict, is_required = _process_single_parameter(p)
        props[name] = prop_dict

        if is_required:
            required.append(name)

    return _build_final_schema(props, required, sub_property)


# ================================= END Parameter to JSON Schema parsing ===================================


def _parameters_to_json_schema(
    parameters: list[Parameter] | set[Parameter] | None,
) -> Dict[str, Any]:
    """
    Turn a set of Parameter instances
    into a JSON Schema dict accepted by litellm.completion.
    """
    if parameters is None:
        return {}
    elif isinstance(parameters, list) and all(
        isinstance(x, Parameter) for x in parameters
    ):
        return _handle_set_of_parameters(parameters)
    elif isinstance(parameters, set) and all(
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

    def model_name(self) -> str:
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
