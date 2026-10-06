"""Runs a decision model for ``decision_node`` and records the call.

The node-side counterpart of ``ModelInvoker``: ``railtracks.classifiers`` models emit
nothing, so the ``decision.*`` events for a node's request are emitted here.
"""

from __future__ import annotations

import uuid
from typing import Any, TypeVar

from railtracks.classifiers import DecisionModel, DecisionResponse, DecisionSchema
from railtracks.classifiers.schema import DecisionState
from railtracks.context.central import get_current_scope, is_context_active
from railtracks.events._resolve import has_enclosing_node
from railtracks.events.decision import (
    DecisionFailureEvent,
    DecisionInvocationEvent,
    DecisionResponseEvent,
)
from railtracks.events.send import emit

_TSchema = TypeVar("_TSchema", bound=DecisionSchema)


async def invoke_decision(
    model: DecisionModel[Any], state: DecisionState, schema: type[_TSchema]
) -> DecisionResponse[_TSchema]:
    """Ask ``model`` about ``state`` and emit the ``decision.*`` events for the call.

    Args:
        model: The decision model to ask.
        state: What to judge: text, or a JSON object or array.
        schema: The schema class declaring the questions.

    Returns:
        The model's response, unchanged.
    """
    # outside a node (a plain script, or a Session body) there is no parent to
    # resolve, and emitting would only log an error
    observed = is_context_active() and has_enclosing_node(get_current_scope())
    decision_id = str(uuid.uuid4())
    if observed:
        await emit(
            DecisionInvocationEvent(
                decision_id=decision_id,
                model_name=model.model_name,
                api_base=model.api_base,
                state=state,
                questions=model.describe_questions(schema),
            )
        )

    try:
        response = await model.aask(state, schema)
    except Exception as e:
        if observed:
            await emit(
                DecisionFailureEvent.from_exception(
                    e, decision_id=decision_id, model_name=model.model_name
                )
            )
        raise

    if observed:
        await emit(
            DecisionResponseEvent(
                decision_id=decision_id,
                model_name=response.requested_model_name,
                reported_model_name=response.model_name,
                provider=response.provider,
                answers=response.structured.encode(),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_cost=response.cost,
                latency=response.latency,
            )
        )
    return response
