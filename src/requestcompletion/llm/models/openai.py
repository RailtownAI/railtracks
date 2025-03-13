from ._llama_index_wrapper import LlamaWrapper
from llama_index.llms.openai import OpenAI
import openai
import json

from ..content import ToolCall
from ..message import AssistantMessage
from ..response import Response
from ..content import ToolCall

class OpenAILLM(LlamaWrapper):
    @classmethod
    def setup_model_object(cls, model_name: str, **kwargs):
        return OpenAI(model_name, **kwargs)

    @classmethod
    def model_type(cls) -> str:
        return "OpenAI"

    @classmethod
    def prepare_tool_calls(cls, tool: ToolCall):
        return {
            "id": tool.identifier,
            "function": {"arguments": json.dumps(tool.arguments), "name": tool.name},
            "type": "function",
        }

    def chat_with_tools(self, messages, tools, **kwargs):
        """
        Chat with the model using tools.
        
        This method preprocesses the kwargs for OpenAI-specific requirements
        before delegating to the parent implementation.
        
        Args:
            messages: The message history to use as context
            tools: The tools to make available to the model
            **kwargs: Additional arguments to pass to the model
            
        Returns:
            A Response object containing the model's response
        """
        # Remove strict parameter if it exists (not supported by OpenAI)
        if "strict" in kwargs:
            del kwargs["strict"]
            
        # Enable parallel tool calls by default for OpenAI
        if "parallel_tool_calls" not in kwargs:
            kwargs["parallel_tool_calls"] = True
            
        # Call the parent implementation which will use our _handle_model_specific_tool_call method
        return super().chat_with_tools(messages, tools, **kwargs)

    def _handle_model_specific_tool_call(self, llama_chat, llama_tools, **kwargs):
        """
        Handle OpenAI-specific tool calls.
        
        Args:
            llama_chat: The chat history in llama format
            llama_tools: The tools in llama format
            **kwargs: Additional arguments to pass to the OpenAI API
            
        Returns:
            A Response object containing the model's response
        """
        
        # Convert our custom tools to OpenAI format
        openai_tools = [tool.to_openai_tool() for tool in llama_tools]
        
        # Convert llama_chat to OpenAI format
        openai_messages = []
        for m in llama_chat:
            message = {"role": m.role}
            if m.content is not None:
                message["content"] = m.content
            if hasattr(m, "additional_kwargs") and m.additional_kwargs:
                for key, value in m.additional_kwargs.items():
                    message[key] = value
            openai_messages.append(message)
        
        # Filter out unsupported parameters
        supported_params = {
            "model", "messages", "tools", "tool_choice", "temperature", 
            "top_p", "n", "stream", "max_tokens", "presence_penalty", 
            "frequency_penalty", "logit_bias", "user", "response_format",
            "parallel_tool_calls"
        }
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported_params}
        
        # Create the completion
        response = openai.chat.completions.create(
            model=self._model_name,
            messages=openai_messages,
            tools=openai_tools,
            **filtered_kwargs
        )
        
        # Process the response
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and choice.message:
                message = choice.message
                
                # Check if there are tool calls
                if hasattr(message, "tool_calls") and message.tool_calls:
                    tool_calls_list = []

                    # I can't forsee how this iterate more than once given how our framework works, but just in case.
                    for tool_call in message.tool_calls:
                        tool_calls_list.append({
                            "tool_id": tool_call.id,
                            "tool_name": tool_call.function.name,
                            "tool_kwargs": json.loads(tool_call.function.arguments)
                        })
                    
                    # Create a response with tool calls
                    assistant_message = AssistantMessage(
                        content=[
                            ToolCall(
                                identifier=t_c["tool_id"], 
                                name=t_c["tool_name"], 
                                arguments=t_c["tool_kwargs"]
                            ) for t_c in tool_calls_list
                        ],
                    )
                    return Response(message=assistant_message)
                else:
                    # Create a response with just text
                    return Response(message=AssistantMessage(content=message.content))
        
        # If we couldn't process the response, return an empty response
        return Response(message=AssistantMessage(content="Error processing OpenAI response"))
