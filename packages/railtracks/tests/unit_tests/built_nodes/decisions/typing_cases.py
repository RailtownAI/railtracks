"""Static cases for decision typing, checked by mypy in ``test_typing.py``.

Never executed. ``# type: ignore[...]`` lines are negative cases: mypy runs with
``--warn-unused-ignores``, so an ignore that stops being needed fails the check.
"""

from __future__ import annotations

import railtracks as rt
from railtracks.built_nodes.decisions import DecisionResponse
from railtracks.decisions import (
    ChoiceAnswer,
    DecisionSchema,
    PredicateAnswer,
    ScoreAnswer,
)
from railtracks.decisions.schema import (
    ChoiceQuestion,
    PredicateQuestion,
    ScoreQuestion,
)
from typing_extensions import assert_type


class Triage(DecisionSchema):
    is_urgent = DecisionSchema.Predicate(instructions="The message conveys urgency")
    department = DecisionSchema.Choice(
        instructions="Which team", choices={"billing": "Money", "technical": "Bugs"}
    )
    frustration = DecisionSchema.Score(
        instructions="How frustrated", levels=["Calm", "Angry"]
    )


class NotASchema:
    pass


jev = rt.decisions.TypeSafeAI(model_name="jev-latest")


def schema_access(triage: Triage) -> None:
    assert_type(Triage.is_urgent, PredicateQuestion)
    assert_type(Triage.department, ChoiceQuestion)
    assert_type(Triage.frustration, ScoreQuestion)

    assert_type(triage.is_urgent, PredicateAnswer)
    assert_type(triage.department, ChoiceAnswer)
    assert_type(triage.frustration, ScoreAnswer)

    assert_type(triage.is_urgent.probability, float)
    assert_type(triage.department.probabilities, dict[str, float])
    assert_type(triage.frustration.probabilities, dict[int, float])

    triage.is_urgent.choice  # type: ignore[attr-defined]


async def direct_call() -> None:
    resp = await jev.aask("I was charged twice", Triage)
    assert_type(resp, DecisionResponse[Triage])
    assert_type(resp.structured.department, ChoiceAnswer)
    assert_type(resp.structured.is_urgent.probability, float)
    assert_type(resp.cost, float | None)

    await jev.aask({"subject": "Duplicate charge"}, Triage)
    await jev.aask("x", NotASchema)  # type: ignore[type-var]


async def node_calls() -> None:
    triage_ticket = rt.decision_node("Triage Ticket", model=jev, schema=Triage)
    result = await rt.call(triage_ticket, "I was charged twice")
    assert_type(result, DecisionResponse[Triage])
    assert_type(result.structured.frustration, ScoreAnswer)

    await rt.call(triage_ticket, state="I was charged twice")
    await rt.call(triage_ticket, {"subject": "Duplicate charge"})

    flow = rt.Flow(name="Ticket Triage", entry_point=triage_ticket)
    assert_type(flow.invoke("x").structured.is_urgent, PredicateAnswer)

    rt.agent_node(
        "Support", llm=rt.llm.OpenAILLM("gpt-5.4-mini"), tool_nodes=[triage_ticket]
    )


async def other_providers() -> None:
    openrouter = rt.decisions.OpenRouterAI("typesafe/jev-1.13")
    luna = rt.decisions.OpenAIDecisions("gpt-6-luna")
    assert_type(await openrouter.aask("x", Triage), DecisionResponse[Triage])
    assert_type(await luna.aask("x", Triage), DecisionResponse[Triage])

    via_luna = rt.decision_node("Triage via Luna", model=luna, schema=Triage)
    assert_type(await rt.call(via_luna, "x"), DecisionResponse[Triage])


def not_a_schema() -> None:
    rt.decision_node("Mismatch", model=jev, schema=NotASchema)  # type: ignore[type-var]
