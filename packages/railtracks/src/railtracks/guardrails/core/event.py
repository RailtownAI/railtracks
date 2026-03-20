from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from railtracks.llm import (
    AssistantMessage,
    MessageHistory,
    SystemMessage,
    ToolCall,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from railtracks.llm.message import Message, Role


class LLMGuardrailPhase(str, Enum):
    INPUT = "llm_input"
    OUTPUT = "llm_output"


def _serialize_content(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(isinstance(c, ToolCall) for c in content):
        return {
            "__type": "tool_calls",
            "data": [tool_call.model_dump(mode="json") for tool_call in content],
        }
    if isinstance(content, ToolResponse):
        return {"__type": "tool_response", "data": content.model_dump(mode="json")}
    if isinstance(content, BaseModel):
        return {
            "__type": "base_model",
            "model_name": content.__class__.__name__,
            "data": content.model_dump(mode="json"),
        }
    return {"__type": "unknown", "data": str(content)}


def _deserialize_content(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if not isinstance(content, dict):
        return content

    content_type = content.get("__type")
    data = content.get("data")

    if content_type == "tool_calls":
        if not isinstance(data, list):
            return []
        return [ToolCall(**tool_call) for tool_call in data]

    if content_type == "tool_response":
        if not isinstance(data, dict):
            raise ValueError("Serialized ToolResponse must contain an object payload.")
        return ToolResponse(**data)

    if content_type == "base_model":
        # We do not attempt dynamic model rehydration in v0.
        return data

    if content_type == "unknown":
        return data

    return content


def _deserialize_message(payload: dict[str, Any]) -> Message:
    role = payload.get("role")
    inject_prompt = bool(payload.get("inject_prompt", True))
    content = _deserialize_content(payload.get("content"))

    if role == Role.user.value:
        if not isinstance(content, str):
            raise ValueError("User messages must deserialize into string content.")
        return UserMessage(content=content, inject_prompt=inject_prompt)
    if role == Role.system.value:
        if not isinstance(content, str):
            raise ValueError("System messages must deserialize into string content.")
        return SystemMessage(content=content, inject_prompt=inject_prompt)
    if role == Role.assistant.value:
        return AssistantMessage(content=content, inject_prompt=inject_prompt)
    if role == Role.tool.value:
        if not isinstance(content, ToolResponse):
            raise ValueError("Tool messages must deserialize into ToolResponse content.")
        return ToolMessage(content=content)

    raise ValueError(f"Unknown serialized message role: {role}")


class LLMGuardrailEvent(BaseModel):
    """
    Event passed to LLM guardrails.

    - ``messages``: conversation context (usually the history *before* the current
      assistant reply is appended to the node).
    - ``output_message``: for ``phase == OUTPUT``, the assistant ``Message`` being
      guarded this turn; ``None`` for INPUT phase or when not applicable.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    phase: LLMGuardrailPhase
    messages: MessageHistory
    output_message: Message | None = None

    node_name: str | None = None
    node_uuid: str | None = None
    run_id: str | None = None
    model_name: str | None = None
    model_provider: str | None = None
    tags: dict[str, str] | None = None

    @field_serializer("messages")
    def _serialize_messages(self, messages: MessageHistory):
        return [
            {
                "role": message.role.value,
                "inject_prompt": message.inject_prompt,
                "content": _serialize_content(message.content),
            }
            for message in messages
        ]

    @field_validator("messages", mode="before")
    @classmethod
    def _deserialize_messages(cls, value: Any):
        if isinstance(value, MessageHistory):
            return value
        if isinstance(value, list) and all(isinstance(m, Message) for m in value):
            return MessageHistory(value)
        if not isinstance(value, list):
            raise ValueError(
                "messages must be a MessageHistory or serialized list of messages."
            )
        return MessageHistory([_deserialize_message(message) for message in value])

    @field_serializer("output_message")
    def _serialize_output_message(self, output_message: Message | None):
        if output_message is None:
            return None
        return {
            "role": output_message.role.value,
            "inject_prompt": output_message.inject_prompt,
            "content": _serialize_content(output_message.content),
        }

    @field_validator("output_message", mode="before")
    @classmethod
    def _deserialize_output_message(cls, value: Any):
        if value is None:
            return None
        if isinstance(value, Message):
            return value
        if isinstance(value, dict):
            return _deserialize_message(value)
        raise ValueError(
            "output_message must be None, a Message, or a serialized message dict."
        )
