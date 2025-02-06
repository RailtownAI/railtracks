from abc import abstractmethod
from typing import List, Callable, Any, Type, Dict

from llama_index.core.llms import ChatMessage
from llama_index.core.tools import FunctionTool, ToolMetadata

import json

from ..model import ModelBase

from ..message import Message
from ..response import Response
from ..history import MessageHistory
from ..message import AssistantMessage, ToolMessage
from ..content import ToolCall, Content
from ..tools import Tool


from pydantic import BaseModel, ValidationError


def _to_llama_chat(message: Message, tool_call_fn: Callable[[ToolCall], Dict]) -> ChatMessage:
    """
    Converts the given `message` to a llama chat message.

    It will handle any possible content type and map it to the proper llama content type.
    """
    # handle the special case where the message is a tool so we have to link it to the tool id.
    if isinstance(message, ToolMessage):
        # TODO: update this logic to be dependency injected
        return ChatMessage(
            content=message.content, role=message.role, additional_kwargs={"tool_call_id": message.identifier}
        )
    # only time this is true is if tool calls
    if isinstance(message.content, list):
        assert all(isinstance(t_c, ToolCall) for t_c in message.content)
        return ChatMessage(
            additional_kwargs={"tool_calls": [tool_call_fn(t_c) for t_c in message.content]}, role=message.role
        )

    # TODO: complete this for the openai case then move one to next step.
    if isinstance(message.content, BaseModel):
        return ChatMessage(content=message.content.model_dump(), role=message.role)

    return ChatMessage(content=message.content, role=message.role)


def _to_llama_tool(tool: Tool) -> FunctionTool:
    """
    Converts the given `tool` to a llama tool.

    Args:
        tool: The tool you would like to convert.

    Returns:
        A `FunctionTool` object that represents the given tool.
    """

    # note we pass in a dummy function becuase we aren't using that part of the llama index API. Function calls should be tracked by RC.
    return FunctionTool(
        fn=lambda *args, **kwargs: None,
        metadata=ToolMetadata(
            name=tool.name,
            description=tool.detail,
            fn_schema=tool.parameters,
        ),
    )


class LlamaWrapper(ModelBase):
    """
    A large base class that wraps around a llama index model.

    Note that the model object should be interacted with via the methods provided in the wrapper class:
    - `chat`
    - `structured`
    - `stream_chat`
    - `chat_with_tools`

    Each individual API should implement the required `abstract_methods` in order to allow users to interact with a
     model of that type.
    """

    def __init__(self, model_name: str, **kwargs):
        """
        Creates a new instance of the model with the provided model_name and any additional kwargs. The kwargs will be
         passed in when you call this model but will be overwritten by any kwargs you provide when you call the model.

        Args:
            model_name: The name of the model you would like to use.
            **kwargs: Any additional arguments you would like to pass to the model when calling it. (These should match
                the arguments that the given API request you have implemented it for.)
        """
        self._model_type = self.model_type()
        self._model_name = model_name
        self.model = self.setup_model_object(model_name, **kwargs)

    @classmethod
    @abstractmethod
    def setup_model_object(cls, model_name: str, **kwargs):
        pass

    @classmethod
    @abstractmethod
    def model_type(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def prepare_tool_calls(cls, tool: ToolCall):
        pass

    def chat(self, messages: MessageHistory, **kwargs):
        """
        Chats with a llama model using the given set of message history.

        Args:
            messages: A complete message history including system messages, that the llm should use as context to
                generate a response.
            **kwargs: Any additional arguments you would like to pass to the model when calling it. These will overwrite
                the arguments passed in at the time of model creation.

        Returns:
            A response object that contains the response from the model. Note the `message` field will be filled and
                the `streamer` field will be empty.
        """
        response = self.model.chat([_to_llama_chat(m, self.prepare_tool_calls) for m in messages], **kwargs)
        return Response(message=AssistantMessage(response.message.content))

    def structured(self, messages: MessageHistory, schema: Type[BaseModel], **kwargs):
        # TODO add a descriptive error for failed structured prediction
        sllm = self.model.as_structured_llm(schema)
        response = sllm.chat([_to_llama_chat(m, self.prepare_tool_calls) for m in messages], **kwargs)

        try:
            return Response(message=AssistantMessage(schema(**json.loads(response.message.content))))
        except ValidationError as e:
            # TODO come up with a better exception message here.
            return Exception()

    def stream_chat(self, messages: MessageHistory, **kwargs):
        message = self.model.stream_chat([_to_llama_chat(m, self.prepare_tool_calls) for m in messages], **kwargs)

        # we need to get creative to map the provided streamer
        def map_to_string():
            for m in message:
                yield m.delta
            return

        return Response(message=None, streamer=map_to_string())

    def chat_with_tools(self, messages: MessageHistory, tools: List[Tool], **kwargs):
        # TODO: add a descriptive error for a tool call with bad parameters.

        llama_tools = [_to_llama_tool(t) for t in tools]
        llama_chat = [_to_llama_chat(m, self.prepare_tool_calls) for m in messages]

        response = self.model.chat_with_tools(
            llama_tools,
            chat_history=llama_chat,
            **kwargs,
        )

        tool_calls = self.model.get_tool_calls_from_response(response, error_on_no_tool_call=False)
        if len(tool_calls) == 0:
            message = AssistantMessage(content=response.message.content)
            return Response(
                message=message,
            )

        message = AssistantMessage(
            content=[
                ToolCall(identifier=t_c.tool_id, name=t_c.tool_name, arguments=t_c.tool_kwargs) for t_c in tool_calls
            ],
        )
        return Response(message=message)

    def __str__(self):
        return f"Model(type={self._model_type}, name={self._model_name})"
