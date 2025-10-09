import json
import time
import warnings
from abc import ABC
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)
import re

import litellm
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import ModelResponse
from pydantic import BaseModel, ValidationError

from ...exceptions.errors import LLMError, NodeInvocationError
from ..content import ToolCall
from ..history import MessageHistory
from ..message import AssistantMessage, Message, ToolMessage
from ..model import ModelBase
from ..response import MessageInfo, Response
from ..tools import Tool
from ..tools.parameters import Parameter


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

    def _generate_cohere_system_prompt(self, schema: Type[BaseModel]) -> str:
        """Generate an optimized system prompt for Cohere based on the schema."""
        schema_info = schema.schema()
        
        # Build field descriptions
        field_descriptions = []
        for field_name, field_info in schema_info["properties"].items():
            field_type = field_info.get("type", "unknown")
            description = field_info.get("description", "")
            field_descriptions.append(f"- {field_name} ({field_type}): {description}")
        
        fields_text = "\n".join(field_descriptions)
        
        prompt = f"""
        You are a structured data API. You MUST respond with ONLY valid JSON that matches this exact schema:
        
        {schema_info}
        
        Field details:
        {fields_text}
        
        CRITICAL INSTRUCTIONS:
        1. Return ONLY the JSON object, no additional text, explanations, or markdown
        2. Do not include ```json ``` code blocks
        3. The response must be directly parseable by json.loads()
        4. All fields must be present and of the correct type
        5. If a field is optional, you may omit it only if no relevant information is available
        6. Do not use **bold**, *italic*, or any other markdown formatting
        7. Do not use numbered lists (1. 2. 3.) or bullet points
        8. Do not include headers, titles, or section names


         FORMATTING PROHIBITIONS:
        - NO **asterisks** for bold
        - NO *asterisks* for italic  
        - NO numbered lists like "1. value"
        - NO bullet points like "- value" or "• value"
        - NO markdown code blocks
        - NO extra text before or after JSON
        
        Example of valid response:
        {json.dumps({k: self._get_example_value(v) for k, v in schema_info["properties"].items()}, indent=2)}

        Example of INVALID response (DO NOT DO THIS):
        Here are the results:
        ```json
        {{
        "numbers": [**282**, **247**, **290**]
        }}
        ```
        
        Example of INVALID response (DO NOT DO THIS):
        1. **282**
        2. **247** 
        3. **290**
        """
        
        return prompt

    def _get_example_value(self, field_info: Dict) -> Any:
        """Generate example values for the schema."""
        field_type = field_info.get("type")
        
        if field_type == "string":
            return "example_string"
        elif field_type == "integer":
            return 42
        elif field_type == "number":
            return 3.14
        elif field_type == "boolean":
            return True
        elif field_type == "array":
            return ["item1", "item2"]
        elif field_type == "object":
            return {"key": "value"}
        else:
            return None

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

        if response_format is not None and "cohere" in self._model_name.lower():
            print('===========COHERE RESPONSE FORMAT==========================')
            print(f'response_format {response_format}')
            print('=====================================')
            # Add schema hint to the prompt (Cohere needs instruction to return JSON)
            if isinstance(response_format, type) and issubclass(response_format, BaseModel):
                system_prompt = self._generate_cohere_system_prompt(response_format)
                print('===========COHERE RESPONSE FORMAT==========================')
                print(f'system_prompt {system_prompt}')
                print('=====================================')
                litellm_messages.insert(0, {
                    "role": "system",
                    "content": system_prompt
                })
        else:
            # For OpenAI etc.
            merged["response_format"] = response_format


        if self.model_type != "OpenAI":
            # Temporary workaround for issue where litellm is looking for response_format in cohere model which is only supported in openai models.
            merged["drop_params"] = True
        print('===========BEFORE LITELLM.COMPLETION==========================')
        print(f'model={self._model_name}, messages={litellm_messages}, stream={stream}, merged={merged}')
        print('=====================================')
        completion = litellm.completion(
            model=self._model_name, messages=litellm_messages, stream=stream, **merged
        )
        print('===========AFTER LITELLM.COMPLETION==========================')
        print(f'completion {completion}')
        print(completion.choices[0].message)
        print('=====================================')


        # 🧩 Handle custom response_format for non-OpenAI models
        if response_format is not None and "cohere" in self._model_name.lower():
            content = completion.choices[0].message.content
            try:
                # If schema is a Pydantic model
                if isinstance(response_format, type) and hasattr(response_format, "__fields__"):
                    import json
                    print('===========BEFORE PARSING CONTENT WHEN PYDANTIC MODEL==========================')
                    print(f'content {content}')
                    print('=====================================')
                    # parsed = response_format(**json.loads(content))
                    extracted_content = self.extract_json(content)
                    parsed = response_format(**json.loads(extracted_content))
                    completion.choices[0].message.content = json.dumps(parsed.dict())
                    # completion.choices[0].message.content = content
                # If it’s a dict-style format
                elif isinstance(response_format, dict):
                    # optional custom logic for dict-style formats
                    pass
            except Exception as e:
                print(f"[WARN] Failed to apply response_format for Cohere: {e}")

        content = completion.choices[0].message.content
        print('===========CONTENT==========================')
        print(content)
        print("============================================")        # Parse the response
        # import re
        # numbers = None
        # if content is not None:
        #     numbers = re.findall(r'\b(\d{3})\b', content)
        # print('===========NUMBERS==========================')
        # print(numbers)
        # print('=====================================')
        mess_info = self.extract_message_info(completion, time.time() - start_time)
        print('===========MESS INFO==========================')
        print(mess_info)
        print('=====================================')
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
        print('===========IN AINVOKE==========================')
        print('===========IN AINVOKE==========================')
        print('===========IN AINVOKE==========================')
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
        print('===========IN STRUCTURED HANDLE BASE==========================')
        print(raw)
        print(info)
        print(schema)
        print('=====================================')
        content_str = raw["choices"][0]["message"]["content"]
        print('===========CONTENT STR==========================')
        print(content_str)
        print('=====================================')

        if "cohere" in self._model_name.lower():
            try:
                # Use our generic extraction system
                extracted_data = self.extract_structured_response(content_str, schema)
                print('===========EXTRACTED DATA==========================')
                print(extracted_data)
                print('=====================================')
                parsed = schema(**extracted_data)
            except Exception as e:
                print(f"Structured extraction failed: {e}")
                # Final fallback: try direct parsing
                try:
                    cleaned_text = self._clean_text_response(content_str)
                    parsed = schema(**json.loads(cleaned_text))
                except:
                    raise ValueError(f"Could not extract structured data: {content_str}")
        else:
            # For OpenAI and others, we assume response_format handled it
            try:
                parsed = schema(**json.loads(content_str))
            except Exception as e:
                raise ValueError(f"Could not parse structured data: {content_str}")

        # parsed = schema(**json.loads('{"numbers": [12, 34, 56]}'))
        # parsed = str(content_str)
        print('===========PARSED==========================')
        print(parsed)
        print('=====================================')
        return Response(message=AssistantMessage(content=parsed), message_info=info)

    def _structured(
        self, messages: MessageHistory, schema: Type[BaseModel], **kwargs
    ) -> Response:
        try:
            print('===========IN STRUCTURED==========================')
            print(f'messages {messages}')
            print(f'schema {schema}')
            print(f'kwargs {kwargs}')
            print('=====================================')
            model_resp, info = self._invoke(messages, response_format=schema, **kwargs)
            print('===========AFTER INVOKE==========================')
            print(f'model_resp {model_resp}')
            print(f'info {info}')
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
        
        
        print('=====================================')
        print(calls)
        print('=====================================')

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


    def extract_structured_response(self, text: str, schema: Type[BaseModel]) -> Dict[str, Any]:
        """
        Extract structured data from Cohere's text response for any schema.
        
        Args:
            text: Raw text response from Cohere
            schema: Pydantic model class defining the expected structure
            
        Returns:
            Dictionary with extracted data matching the schema
        """
        print('===========EXTRACTING STRUCTURED RESPONSE==========================')
        print(f"Input text: {text}")
        print(f"Target schema: {schema.__name__}")

        # Clean the text response
        cleaned_text = self._clean_text_response(text)
        print(f"Cleaned text: {cleaned_text}")
        
        # Try to extract JSON first
        json_data = self._extract_json(cleaned_text)
        if json_data and self._validate_against_schema(json_data, schema):
            print("Successfully extracted JSON matching schema")
            return json_data
        
        # Text-based extraction for the schema
        extracted_data = self._extract_from_text_by_schema(cleaned_text, schema)
        if extracted_data and self._validate_against_schema(extracted_data, schema):
            print("Successfully extracted data from text")
            return extracted_data
        
         # Strategy 3: Fallback - use original text with enhanced parsing
        enhanced_data = self._enhanced_text_parsing(text, schema)
        if enhanced_data:
            print("Successfully parsed with enhanced parsing")
            return enhanced_data
        
        # Fallback - use LLM to fix the response (advanced)
        fixed_data = self._fix_response_with_llm(text, schema)
        if fixed_data:
            print("Successfully fixed response with LLM")
            return fixed_data
            
        raise ValueError(f"Could not extract structured data from response: {text}")
    
    #======================================================

    def _enhanced_text_parsing(self, text: str, schema: Type[BaseModel]) -> Optional[Dict[str, Any]]:
        """
        Enhanced parsing that handles markdown-formatted responses specifically.
        """
        schema_info = schema.schema()
        properties = schema_info["properties"]
        extracted_data = {}
        
        for field_name, field_info in properties.items():
            field_type = field_info.get("type")
            
            if field_type == "array":
                # Enhanced array extraction that handles markdown lists
                items = self._extract_array_enhanced(text, field_info)
                extracted_data[field_name] = items
                
            elif field_type in ["integer", "number"]:
                # Enhanced number extraction that ignores markdown
                numbers = self._extract_numbers_ignoring_markdown(text)
                if numbers:
                    extracted_data[field_name] = numbers[0]  # Take first number
                
            elif field_type == "string":
                # Enhanced string extraction
                value = self._extract_string_ignoring_markdown(text, field_name)
                extracted_data[field_name] = value
        
        return extracted_data if extracted_data else None

    def _extract_array_enhanced(self, text: str, field_info: Dict) -> List:
        """Enhanced array extraction that handles markdown lists."""
        items_info = field_info.get("items", {})
        item_type = items_info.get("type")
        
        # Extract all potential items using multiple patterns
        all_items = []
        
        # Pattern 1: Numbered lists with markdown (1. **value**)
        numbered_markdown = re.findall(r'(?:\d+[\.\)]\s*)\*?\*?([^*\n]+)\*?\*?', text)
        all_items.extend([item.strip() for item in numbered_markdown])
        
        # Pattern 2: Bullet points with markdown (- **value**)
        bullet_markdown = re.findall(r'(?:[-•*]\s*)\*?\*?([^*\n]+)\*?\*?', text)
        all_items.extend([item.strip() for item in bullet_markdown])
        
        # Pattern 3: Items in quotes or other formatting
        quoted_items = re.findall(r'["\']([^"\']+)["\']', text)
        all_items.extend(quoted_items)
        
        # Pattern 4: Plain numbers (for numeric arrays)
        if item_type in ["integer", "number"]:
            numbers = re.findall(r'\b\d+\b', text)
            all_items.extend(numbers)
        
        # Convert to appropriate types
        if item_type == "integer":
            return [int(item) for item in all_items if item.strip().isdigit()]
        elif item_type == "number":
            return [float(item) for item in all_items if self._is_numeric(item)]
        else:
            return [item for item in all_items if item.strip()]

    def _extract_numbers_ignoring_markdown(self, text: str) -> List[Union[int, float]]:
        """Extract numbers while ignoring markdown formatting."""
        # Remove markdown first, then extract numbers
        clean_text = self._remove_markdown_formatting(text)
        numbers = re.findall(r'\b\d+\b', clean_text)
        return [int(num) for num in numbers]

    def _extract_string_ignoring_markdown(self, text: str, field_name: str) -> str:
        """Extract strings while ignoring markdown formatting."""
        clean_text = self._remove_markdown_formatting(text)
        
        # Look for field name followed by value
        pattern = rf"{field_name}[\s:]+([^\n\.]+)"
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return ""

    def _is_numeric(self, text: str) -> bool:
        """Check if text can be converted to numeric."""
        try:
            float(text)
            return True
        except ValueError:
            return False
    
    #======================================================


    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text using multiple strategies."""
        # Direct JSON parsing
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Extract JSON object/array using regex
        json_patterns = [
            r'\{[^{}]*\{[^{}]*\}[^{}]*\}',  # Nested objects
            r'\{[^{}]*\[[^]]*\][^{}]*\}',   # Objects with arrays
            r'\{.*\}',                      # Simple objects
            r'\[.*\]',                      # Arrays
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def _extract_from_text_by_schema(self, text: str, schema: Type[BaseModel]) -> Dict[str, Any]:
        """
        Extract data from text based on schema field types and names.
        """
        schema_info = schema.schema()
        properties = schema_info["properties"]
        extracted_data = {}
        
        for field_name, field_info in properties.items():
            field_type = field_info.get("type")
            field_description = field_info.get("description", "")
            
            print(f"Extracting field: {field_name} (type: {field_type})")
            
            # Extract based on field type
            if field_type == "array":
                extracted_data[field_name] = self._extract_array_field(text, field_name, field_info)
            elif field_type == "string":
                extracted_data[field_name] = self._extract_string_field(text, field_name, field_info)
            elif field_type in ["integer", "number"]:
                extracted_data[field_name] = self._extract_numeric_field(text, field_name, field_info)
            elif field_type == "boolean":
                extracted_data[field_name] = self._extract_boolean_field(text, field_name, field_info)
            elif field_type == "object":
                extracted_data[field_name] = self._extract_object_field(text, field_name, field_info)
            else:
                # Try generic extraction
                extracted_data[field_name] = self._extract_generic_field(text, field_name, field_info)
        
        return extracted_data
    
    def _extract_array_field(self, text: str, field_name: str, field_info: Dict) -> List:
        """Extract array fields based on context."""
        items_info = field_info.get("items", {})
        
        # Look for numbered lists
        numbered_items = re.findall(r'(?:\d+\.\s*)([^\n\.]+)', text)
        if numbered_items:
            return [item.strip() for item in numbered_items]
        
        # Look for bullet points
        bullet_items = re.findall(r'(?:[-•*]\s*)([^\n]+)', text)
        if bullet_items:
            return [item.strip() for item in bullet_items]
        
        # Look for items in brackets
        bracket_items = re.findall(r'\[([^]]+)\]', text)
        if bracket_items:
            items = [item.strip() for item in bracket_items[0].split(',')]
            return items
        
        # Extract based on item type
        if items_info.get("type") == "integer":
            numbers = re.findall(r'\b\d+\b', text)
            return [int(n) for n in numbers[:10]]  # Limit to first 10
        elif items_info.get("type") == "number":
            # Match floats and integers (e.g., 3, 3.14, .5, 0.001)
            floats = re.findall(r'\b\d+\.\d+|\b\d+\b', text)
            return [float(n) for n in floats[:10]]
        
        return []
    
    def _extract_string_field(self, text: str, field_name: str, field_info: Dict) -> str:
        """Extract string fields based on context."""
        # Look for field name followed by value
        pattern = rf"{field_name}[\s:]+([^\n\.]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # For names, look for capitalized words
        if "name" in field_name.lower():
            name_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
            names = re.findall(name_pattern, text)
            if names:
                return names[0]
        
        return ""
    
    def _extract_numeric_field(self, text: str, field_name: str, field_info: Dict) -> Optional[float]:
        """Extract numeric fields."""
        # Look for field name followed by number
        pattern = rf"{field_name}[\s:]+(\d+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        
        # Extract all numbers and take the most relevant one
        numbers = re.findall(r'\b\d+\b', text)
        if numbers:
            return float(numbers[0])
        
        return None
    
    def _extract_boolean_field(self, text: str, field_name: str, field_info: Dict) -> bool:
        """Extract boolean fields."""
        # Look for yes/no, true/false patterns
        true_patterns = [r'\byes\b', r'\btrue\b', r'\bcorrect\b', r'\baccurate\b', r'\bright\b']
        false_patterns = [r'\bno\b', r'\bfalse\b', r'\bincorrect\b', r'\bwrong\b']
        
        for pattern in true_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        for pattern in false_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        return False
    
    def _extract_object_field(self, text: str, field_name: str, field_info: Dict) -> Dict:
        """Extract nested object fields."""
        # Look for JSON-like structures for the object
        json_data = self._extract_json(text)
        if json_data and field_name in json_data:
            return json_data[field_name]
        
        return {}
    
    def _extract_generic_field(self, text: str, field_name: str, field_info: Dict) -> Any:
        """Generic field extraction as fallback."""
        # Try to find the field name followed by some value
        pattern = rf"{field_name}[\s:]+([^\n\.]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _validate_against_schema(self, data: Dict[str, Any], schema: Type[BaseModel]) -> bool:
        """Validate extracted data against schema."""
        try:
            # Try to create an instance of the schema
            schema(**data)
            return True
        except Exception as e:
            print(f"Validation failed: {e}")
            return False
    
    def _fix_response_with_llm(self, text: str, schema: Type[BaseModel]) -> Optional[Dict[str, Any]]:
        """
        Use the LLM itself to fix malformed responses (advanced fallback).
        """
        try:
            schema_json = schema.schema_json(indent=2)
            
            fix_prompt = f"""
            The following text was supposed to be a response matching this JSON schema:
            {schema_json}
            
            But the response was malformed:
            {text}
            
            Please extract the relevant information and return ONLY valid JSON that matches the schema exactly.
            Do not include any explanations or additional text.
            """
            
            # Use a quick LLM call to fix the response
            fixed_response = litellm.completion(
                model=self._model_name,
                messages=[{"role": "user", "content": fix_prompt}],
                max_tokens=500,
                temperature=0.1
            )
            
            fixed_content = fixed_response.choices[0].message.content
            return json.loads(fixed_content)
            
        except Exception as e:
            print(f"LLM fixing failed: {e}")
            return None 
        
    def _clean_text_response(self, text: str) -> str:
        """
        Remove markdown formatting and clean text for better parsing.
        
        Handles:
        - **bold** text → removes asterisks
        - *italic* text → removes asterisks  
        - Numbered lists (1. 2. 3.) → extracts values
        - Bullet points (-, •, *) → extracts values
        - Markdown code blocks (```json ```) → extracts content
        - Extra whitespace and newlines
        """
        print('===========CLEANING TEXT RESPONSE==========================')
        print(f"Original text: {repr(text)}")
        
        # Remove markdown code blocks and extract content
        text = self._remove_markdown_code_blocks(text)
        
        # Remove bold and italic formatting (**text** -> text)
        text = self._remove_markdown_formatting(text)
        
        # Extract content from numbered lists
        text = self._extract_from_numbered_lists(text)
        
        # Extract content from bullet points  
        text = self._extract_from_bullet_points(text)
        
        # Clean whitespace
        text = self._clean_whitespace(text)
        
        print(f"Cleaned text: {repr(text)}")
        print('=====================================')
        return text

    def _remove_markdown_code_blocks(self, text: str) -> str:
        """Remove markdown code blocks and extract content."""
        # Remove ```json ... ``` blocks and extract content
        code_block_pattern = r'```(?:json)?\s*(.*?)\s*```'
        matches = re.findall(code_block_pattern, text, re.DOTALL)
        if matches:
            # If we found code blocks, use the first one's content
            return matches[0].strip()
        return text

    def _remove_markdown_formatting(self, text: str) -> str:
        """Remove bold (**) and italic (*) markdown formatting."""
        # Remove **bold** but keep the text
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        
        # Remove *italic* but keep the text  
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        
        # Remove other common markdown
        text = re.sub(r'__([^_]+)__', r'\1', text)  # __underline__
        text = re.sub(r'~~([^~]+)~~', r'\1', text)  # ~~strikethrough~~
        
        return text

    def _extract_from_numbered_lists(self, text: str) -> str:
        """Extract values from numbered lists and format as array."""
        # Find numbered list patterns: "1. value", "2) value", etc.
        numbered_pattern = r'(?:\d+[\.\)]\s*)([^\n]+)'
        matches = re.findall(numbered_pattern, text)
        
        if matches:
            # If we find a numbered list, create a JSON array
            cleaned_items = [self._clean_text_response(item.strip()) for item in matches]
            return json.dumps(cleaned_items)
        
        return text

    def _extract_from_bullet_points(self, text: str) -> str:
        """Extract values from bullet points and format as array."""
        # Find bullet points: "- item", "• item", "* item"
        bullet_pattern = r'(?:[-•*]\s*)([^\n]+)'
        matches = re.findall(bullet_pattern, text)
        
        if matches:
            # If we find bullet points, create a JSON array
            cleaned_items = [self._clean_text_response(item.strip()) for item in matches]
            return json.dumps(cleaned_items)
        
        return text

    def _clean_whitespace(self, text: str) -> str:
        """Clean up excessive whitespace."""
        # Replace multiple newlines with single space
        text = re.sub(r'\n+', ' ', text)
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


_T = TypeVar("_T")


def _return_none_on_error(func: Callable[[], _T]) -> _T:
    try:
        return func()
    except:  # noqa: E722
        return None
