"""Pure functions converting domain objects to persistence rows.

These mirror the per-type encoders in `railtracks.state.serialize`
(`encode_failure`, `encode_tool_call`, ...) and reuse them directly —
the encoder functions remain the canonical dict-shapers; the mappers
flatten their output into columns.

Mappers never touch the database. Anything that needs a generated key
(``llm_calls.call_id``, ``messages.message_id``) is threaded in by the
repository after the parent row is flushed.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from railtracks.built_nodes.concrete import RequestDetails
from railtracks.llm import Message, ToolCall, ToolResponse, UserMessage
from railtracks.state.node import LinkedNode
from railtracks.state.request import Cancelled, Failure, RequestTemplate
from railtracks.state.serialize import (
    RTJSONEncoder,
    encode_base_model,
    encode_content,
    encode_failure,
    encode_message,
    encode_tool_call,
)
from railtracks.utils.profiling import Stamp

from .models import (
    FailureRow,
    LLMCallRow,
    NodeRow,
    NodeVersionRow,
    RequestRow,
    StampRow,
)


def jsonable(value: Any) -> Any:
    """Round-trip an arbitrary value through RTJSONEncoder.

    Guarantees the result is JSON-storable, with the exact same shape the
    JSON file format used — including the string fallback for types the
    encoder doesn't know.
    """
    if value is None:
        return None
    return json.loads(json.dumps(value, cls=RTJSONEncoder))


def output_kind_of(output: Any) -> str:
    if output is None:
        return "open"
    if isinstance(output, Failure):
        return "failure"
    if isinstance(output, Cancelled):
        return "cancelled"
    return "value"


def linked_node_to_rows(
    ln: LinkedNode, run_id: str
) -> tuple[NodeRow, list[NodeVersionRow]]:
    """Unroll a LinkedNode's temporal parent chain into one node row plus
    one version row per snapshot (oldest first)."""
    chain: list[LinkedNode] = []
    current: LinkedNode | None = ln
    while current is not None:
        chain.append(current)
        current = current.parent
    chain.reverse()

    # name()/type() are classmethods; calling them on the wrapped instance
    # avoids LinkedNode.node's safe_copy (which can raise NodeCopyError).
    node = ln._node
    node_row = NodeRow(
        node_uuid=ln.identifier,
        run_id=run_id,
        name=node.name(),
        node_type=node.type(),
    )
    version_rows = [
        NodeVersionRow(
            node_uuid=ln.identifier,
            stamp_step=v.stamp.step,
            stamp_time=v.stamp.time,
            stamp_identifier=v.stamp.identifier,
        )
        for v in chain
    ]
    return node_row, version_rows


def request_to_rows(
    rt: RequestTemplate, run_id: str
) -> tuple[RequestRow, FailureRow | None]:
    """Map the latest version of a request to a row.

    The temporal parent chain collapses: the row carries the creation stamp
    (oldest version) and the latest stamp. `parent_request_id` is reserved
    for genuine request-to-request relationships, not temporal history, and
    is left unset here.
    """
    oldest = rt.get_all_parents()[-1]
    kind = output_kind_of(rt.output)

    failure_row = None
    output_json = None
    if kind == "failure":
        encoded = encode_failure(rt.output)
        failure_row = FailureRow(
            request_id=rt.identifier,
            exception_type=encoded["type"],
            message=encoded["message"],
            traceback=encoded["traceback"],
        )
    elif kind == "value":
        output_json = jsonable(rt.output)

    request_row = RequestRow(
        request_id=rt.identifier,
        run_id=run_id,
        source_node_uuid=rt.source_id,
        sink_node_uuid=rt.sink_id,
        input_args_json=jsonable(list(rt.input[0])),
        input_kwargs_json=jsonable(rt.input[1]),
        output_json=output_json,
        output_kind=kind,
        status=rt.status,
        created_stamp_step=oldest.stamp.step,
        created_stamp_time=oldest.stamp.time,
        stamp_step=rt.stamp.step,
        stamp_time=rt.stamp.time,
    )
    return request_row, failure_row


def stamp_to_row(stamp: Stamp, session_id: str) -> StampRow:
    return StampRow(
        session_id=session_id,
        step=stamp.step,
        time=stamp.time,
        identifier=stamp.identifier,
    )


def llm_details_to_call_row(
    details: RequestDetails,
    *,
    node_uuid: str,
    session_id: str,
    call_index: int,
) -> LLMCallRow:
    provider = details.model_provider
    return LLMCallRow(
        node_uuid=node_uuid,
        session_id=session_id,
        call_index=call_index,
        model_name=details.model_name or "unknown",
        model_provider=str(provider) if provider is not None else None,
        input_tokens=details.input_tokens,
        output_tokens=details.output_tokens,
        total_cost=details.total_cost,
        system_fingerprint=details.system_fingerprint,
        latency=details.latency,
    )


def classify_message(
    message: Message,
) -> tuple[str, str | None, Any, list[ToolCall], ToolResponse | None]:
    """Break a Message into storable parts.

    Returns (content_kind, content_text, content_json, tool_calls,
    tool_response). The tool_calls / tool_response components let the
    repository create the normalized child rows.
    """
    content = message.content

    if isinstance(content, ToolResponse):
        return "tool_response", None, encode_content(content), [], content

    if isinstance(content, list) and content and all(
        isinstance(c, ToolCall) for c in content
    ):
        return (
            "tool_calls",
            None,
            [encode_tool_call(c) for c in content],
            list(content),
            None,
        )

    if isinstance(content, BaseModel):
        return "model", None, encode_base_model(content), [], None

    if isinstance(content, str):
        if isinstance(message, UserMessage) and message.attachment is not None:
            # encode_message expands attachments into the content list shape.
            return "text", content, encode_message(message)["content"], [], None
        return "text", content, None, [], None

    return "text", str(content), None, [], None
