from abc import abstractmethod
from typing import List, Callable, Any, Type, Dict, Optional

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


# Custom tool class that works with our implementation
class CustomTool:
    """A simple tool class that can be used with LlamaIndex"""
    
    def __init__(self, name: str, description: str, schema: Dict):
        self.name = name
        self.description = description
        self.schema = schema
        
    def to_openai_tool(self):
        """Convert to OpenAI tool format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema
            }
        }


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


def _to_llama_tool(tool: Tool) -> CustomTool:
    """
    Converts the given `tool` to a custom tool.

    Args:
        tool: The tool you would like to convert.

    Returns:
        A `CustomTool` object that represents the given tool.
    """
    # Get the schema from the tool's parameters
    schema = None
    if tool.parameters:
        if hasattr(tool.parameters, "model_json_schema"):
            # If it's a Pydantic model, get the schema
            schema = tool.parameters.model_json_schema()
            
            # Ensure additionalProperties is set to false for OpenAI compatibility
            if "additionalProperties" not in schema:
                schema["additionalProperties"] = False
        elif isinstance(tool.parameters, dict):
            # If it's already a dict, use it directly
            schema = tool.parameters
            if "additionalProperties" not in schema:
                schema["additionalProperties"] = False
            if "type" not in schema:
                schema["type"] = "object"
    
    # If we couldn't get a schema, create a minimal valid one
    if not schema:
        schema = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        }
    
    # Use our custom tool class
    return CustomTool(
        name=tool.name,
        description=tool.detail,
        schema=schema
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
        """
        Chat with the model using tools.
        
        Args:
            messages: The message history to use as context
            tools: The tools to make available to the model
            **kwargs: Additional arguments to pass to the model
            
        Returns:
            A Response object containing the model's response
        """
        # Convert our tools and messages to the format expected by the underlying implementation
        llama_tools = [_to_llama_tool(t) for t in tools]
        llama_chat = [_to_llama_chat(m, self.prepare_tool_calls) for m in messages]
        
        # TODO: Supporting OpenAI for now
        try:
            # Try to use the model-specific implementation if available
            return self._handle_model_specific_tool_call(llama_chat, llama_tools, **kwargs)
        except NotImplementedError:
            # Fall back to the default implementation if the model-specific one is not available
            pass
        
        # Default implementation for most models
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

    def _handle_model_specific_tool_call(self, llama_chat, llama_tools, **kwargs):
        """
        Optional method for model-specific tool call handling.
        
        Subclasses can implement this method to provide custom tool call handling
        for specific model types. If implemented, chat_with_tools will use this
        implementation instead of the default one.
        
        Args:
            llama_chat: The chat history in llama format
            llama_tools: The tools in llama format
            **kwargs: Additional arguments to pass to the model
            
        Returns:
            A Response object containing the model's response
        """
        raise NotImplementedError("This model does not implement model-specific tool call handling")

    def __str__(self):
        return f"Model(type={self._model_type}, name={self._model_name})"
