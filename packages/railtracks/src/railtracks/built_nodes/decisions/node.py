from __future__ import annotations

from typing import Callable, Iterable, ParamSpec, cast

from railtracks.decisions import DecisionModel, DecisionResponse, DecisionSchema
from railtracks.decisions.state import DecisionInput
from railtracks.exceptions import NodeCreationError
from railtracks.llm import Parameter, Tool
from railtracks.middleware.core import Middleware
from railtracks.nodes.nodes import Node

from ..function.node_builder import FunctionNodeBuilder
from .invoker import invoke_decision

_P = ParamSpec("_P")
STATE_DESCRIPTION = "The text to judge."


def _state_shape(state: DecisionInput) -> object:
    """Never called: gives `_P` a named ``state`` parameter, as `_user_input_shape` does
    for `agent_node`."""
    raise NotImplementedError


def decision_node(
    name: str | None = None,
    *,
    model: DecisionModel,
    schema: DecisionSchema,
    description: str | None = None,
    middleware: Iterable[Middleware[_P, DecisionResponse]] | None = None,
    _shape: Callable[_P, object] = _state_shape,
) -> type[Node[_P, DecisionResponse]]:
    """Create a node that answers ``schema``'s questions about a state with ``model``.

    The System One counterpart of `agent_node`. The node is a Tool: use it as a Flow's
    entry point, with `rt.call`/`rt.call_batch`, or in an agent's ``tool_nodes``, where
    the agent reads the response's compact ``str()``.

    Args:
        name (str | None): The node and tool name. Defaults to "Decision".
        model (DecisionModel): The decision model, e.g. `rt.decisions.TypeSafeAI`,
            `rt.decisions.OpenRouterAI` or `rt.decisions.OpenAIDecisions`.
        schema (DecisionSchema): The questions to answer, as a `DecisionSchema`;
            every model answers any schema.
        description (str | None): The tool description an agent sees. Defaults to a
            sentence listing each question's instructions.
        middleware (Iterable[Middleware] | None): Middleware applied around the node
            boundary (state -> DecisionResponse).
        _shape (Callable[_P, object]): Internal use only. Used to infer the ParamSpec for
            the node's input shape.

    Raises:
        NodeCreationError: If the name is blank, the model is not a `DecisionModel`, or
            the schema is not a `DecisionSchema`.
    """
    _validate(name, model, schema)
    node_name = name if name is not None else "Decision"
    detail = description if description is not None else _default_detail(schema)

    # `str` so TypeMapper coerces an agent's tool argument; Python callers may pass JSON
    async def invoke(state: str) -> DecisionResponse:
        return await invoke_decision(model, state, schema)

    tool = Tool(
        name=node_name.replace(" ", "_"),
        detail=detail,
        parameters=[
            Parameter(name="state", description=STATE_DESCRIPTION, param_type="string")
        ],
    )
    builder = FunctionNodeBuilder.function(
        invoke,
        class_name="".join(node_name.split()),
        name=node_name,
        tool_info=tool,
        middleware=cast(
            Iterable[Middleware[[str], DecisionResponse]] | None,
            middleware,
        ),
    )
    return cast(type[Node[_P, DecisionResponse]], builder.build())


def _validate(name: str | None, model: DecisionModel, schema: DecisionSchema) -> None:
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise NodeCreationError(
            message=f"decision_node name must be a non-empty string, got {name!r}.",
            notes=['Omit name to use "Decision".'],
        )
    if not isinstance(model, DecisionModel):
        raise NodeCreationError(
            message=f"decision_node model must be a decision model such as rt.decisions.TypeSafeAI, got {type(model).__name__}.",
        )
    if not isinstance(schema, DecisionSchema):
        raise NodeCreationError(
            message=f"decision_node needs a DecisionSchema as its schema, got {schema!r}.",
            notes=["Build one with rt.decisions.DecisionSchema(predicate=[...], ...)."],
        )


def _default_detail(schema: DecisionSchema) -> str:
    questions = "; ".join(
        f"{name}: {question.instructions}"
        for name, question in schema.questions.items()
    )
    return (
        "Answers these questions about the given text with calibrated "
        f"probabilities. {questions}."
    )
