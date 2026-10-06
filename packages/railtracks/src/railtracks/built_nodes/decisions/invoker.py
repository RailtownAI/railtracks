"""Runs a decision model for ``decision_node``, records the call and classifies errors.

The node-side counterpart of ``ModelInvoker`` and ``llm_helpers``: ``railtracks.decisions``
models emit nothing and raise ``ClassifierError``; here a node's request gets its
``decision.*`` events, and a failure becomes the ``DecisionModelError`` users catch.
"""

from __future__ import annotations

import uuid
from typing import Any, TypeVar

from railtracks.context.central import get_current_scope, is_context_active
from railtracks.decisions import (
    ClassifierAuthenticationError,
    ClassifierConnectionError,
    ClassifierError,
    ClassifierRateLimitError,
    ClassifierRequestError,
    ClassifierResponseError,
    ClassifierServerError,
    ClassifierTimeoutError,
    DecisionModel,
    DecisionResponse,
    DecisionSchema,
)
from railtracks.decisions.schema import DecisionState
from railtracks.events._resolve import has_enclosing_node
from railtracks.events.decision import (
    DecisionFailureEvent,
    DecisionInvocationEvent,
    DecisionResponseEvent,
)
from railtracks.events.send import emit
from railtracks.exceptions import (
    DecisionAuthenticationError,
    DecisionModelError,
    DecisionRateLimitError,
    DecisionRequestError,
    DecisionResponseError,
    DecisionServerError,
    DecisionTimeoutError,
)

_TSchema = TypeVar("_TSchema", bound=DecisionSchema)

# Ordered most-specific first. ClassifierRequestError is handled apart (it carries a body).
_CLASSIFIER_TO_NODE_ERROR: tuple[
    tuple[type[ClassifierError], type[DecisionModelError]], ...
] = (
    (ClassifierAuthenticationError, DecisionAuthenticationError),
    (ClassifierRateLimitError, DecisionRateLimitError),
    (ClassifierTimeoutError, DecisionTimeoutError),
    (ClassifierConnectionError, DecisionTimeoutError),
    (ClassifierServerError, DecisionServerError),
    (ClassifierResponseError, DecisionResponseError),
)


def _node_error_for(error: ClassifierError) -> DecisionModelError:
    """The node-terminating error a failed decision call surfaces as."""
    if isinstance(error, ClassifierRequestError):
        return DecisionRequestError(
            error.reason, body=error.body, notes=list(error.notes)
        )
    for classifier_type, node_type in _CLASSIFIER_TO_NODE_ERROR:
        if isinstance(error, classifier_type):
            return node_type(error.reason, notes=list(error.notes))
    return DecisionModelError(error.reason, notes=list(error.notes))


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

    Raises:
        DecisionModelError: If the call fails; the subclass mirrors the model's
            ``ClassifierError``, which is kept as ``__cause__``.
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
                # None until configured; the call then fails with a request error
                api_base=model.api_base or "",
                state=state,
                questions=model.describe_questions(schema),
            )
        )

    try:
        response = await model.aask(state, schema)
    except Exception as e:
        if observed:
            # the model's own error, before translation, is what the record keeps
            await emit(
                DecisionFailureEvent.from_exception(
                    e, decision_id=decision_id, model_name=model.model_name
                )
            )
        if isinstance(e, ClassifierError):
            raise _node_error_for(e) from e
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
