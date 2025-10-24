from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from railtracks.built_nodes.concrete import RequestDetails
from railtracks.llm import Message, ToolCall, ToolResponse, UserMessage
from railtracks.nodes.nodes import LatencyDetails
from railtracks.utils.profiling import Stamp
from railtracks.utils.serialization.graph import Edge, Vertex

supported_types = (
    Message,
    ToolResponse,
    Edge,
    Vertex,
    RequestDetails,
    Stamp,
    ToolCall,
    LatencyDetails,
    BaseModel,
)


# Consider refactoring this function to use a mapping of types to encoding functions for better scalability and maintainability.
def encoder_extender(o) -> dict[str, Any]:
    """
    Extends the encoding of supported types to their dictionary representation.

    We support the following types as of right now:
    - Edge
    - Vertex
    - Stamp
    - RequestDetails
    - Message
    - ToolResponse
    - ToolCall
    - LatencyDetails
    - BaseModel (Pydantic models)
    """
    if isinstance(o, Edge):
        return encode_edge(o)
    elif isinstance(o, Vertex):
        return encode_vertex(o)
    elif isinstance(o, Stamp):
        return encode_stamp(o)
    elif isinstance(o, RequestDetails):
        return encode_request_details(o)
    elif isinstance(o, Message):
        return encode_message(o)
    elif isinstance(o, ToolResponse):
        return encode_content(o)
    elif isinstance(o, ToolCall):
        return encode_tool_call(o)
    elif isinstance(o, LatencyDetails):
        return encode_latency_details(o)
    elif isinstance(o, BaseModel):
        return encode_base_model(o)
    else:
        raise TypeError(f"Unsupported type: {type(o)}")


def encode_tool_call(tool_call: ToolCall):
    """
    Encodes a ToolCall object to a dictionary representation.
    """
    return {
        "identifier": tool_call.identifier,
        "name": tool_call.name,
        "arguments": tool_call.arguments,
    }


def encode_latency_details(latency_details: LatencyDetails):
    """
    Encodes LatencyDetails to a dictionary representation.
    """
    return {
        "total_time": latency_details.total_time,
    }


def encode_edge(edge: Edge) -> dict[str, Any]:
    """
    Encodes an Edge object to a dictionary representation.
    """
    return {
        "source": edge.source,
        "target": edge.target,
        "identifier": edge.identifier,
        "stamp": edge.stamp,
        "details": edge.details,
        "parent": edge.parent,
    }


def encode_vertex(vertex: Vertex) -> dict[str, Any]:
    """
    Encodes a Vertex object to a dictionary representation.
    """
    return {
        "identifier": vertex.identifier,
        "node_type": vertex.node_type,
        "name": vertex.name,
        "stamp": vertex.stamp,
        "details": vertex.details,
        "parent": vertex.parent,
    }


def encode_stamp(stamp: Stamp) -> dict[str, Any]:
    """
    Encodes a Stamp object to a dictionary representation.
    """
    return {
        "step": stamp.step,
        "time": stamp.time,
        "identifier": stamp.identifier,
    }


def encode_request_details(details: RequestDetails) -> dict[str, Any]:
    """
    Encodes a RequestDetails object to a dictionary representation.
    """
    return {
        "model_name": details.model_name,
        "model_provider": details.model_provider,
        "input": details.input,
        "output": details.output,
        "input_tokens": details.input_tokens,
        "output_tokens": details.output_tokens,
        "total_cost": details.total_cost,
        "system_fingerprint": details.system_fingerprint,
        "latency": details.latency,
    }


def encode_message(message: Message) -> dict[str, Any]:
    """
    Encodes a Message object to a dictionary representation.
    """
    if isinstance(message, UserMessage) and message.attachment is not None:
        attachment = [
            {
                "modality": msg_attachment.modality,
                "type": msg_attachment.type,
                "info": msg_attachment.url,
            }
            for msg_attachment in message.attachment
        ]

        return {
            "role": message.role.value,
            "content": [{"type": "text", "text": message.content}, *attachment],
        }
    else:
        return {
            "role": message.role.value,
            "content": message.content,
        }


def encode_content(content: ToolResponse):
    return {
        "identifier": content.identifier,
        "name": content.name,
        "result": content.result,
    }


def encode_base_model(model: BaseModel):
    """
    Encodes a BaseModel object to a dictionary representation.
    """
    return model.model_dump()  # Use Pydantic's model_dump method for serialization


class RTJSONEncoder(json.JSONEncoder):
    """
    A custom JSON encoder that extends the default JSONEncoder to handle specific types used in the system.

    Please consult `supported_types` for the list of supported types.
    """

    def default(self, o):
        if isinstance(o, supported_types):
            return encoder_extender(o)

        try:
            return super().default(o)
        except TypeError:
            return f"ERROR: w/ type {type(o)}" + str(
                o
            )  # Fallback to string representation for non-serializable objects
