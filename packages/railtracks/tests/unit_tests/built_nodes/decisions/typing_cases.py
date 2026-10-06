"""Static cases for decision typing, checked by mypy in ``test_typing.py``.

Never executed. ``# type: ignore[...]`` lines are negative cases: mypy runs with
``--warn-unused-ignores``, so an ignore that stops being needed fails the check.
"""

from __future__ import annotations

import railtracks as rt
from railtracks.built_nodes.decisions import DecisionResponse
from railtracks.decisions import (
    ChoiceAnswer,
    NoulAnswer,
    ScoreAnswer,
    TypeSafeSchema,
)
from railtracks.decisions.models.system_one.schema import (
    ChoiceQuestion,
    NoulQuestion,
    ScoreQuestion,
)
from railtracks.decisions.schema import DecisionQuestion, DecisionSchema
from typing_extensions import assert_type


class Triage(TypeSafeSchema):
    is_urgent = TypeSafeSchema.Noul(instructions="The message conveys urgency")
    department = TypeSafeSchema.Choice(
        instructions="Which team", criteria={"billing": "Money", "technical": "Bugs"}
    )
    frustration = TypeSafeSchema.Score(
        instructions="How frustrated", criteria=["Calm", "Angry"]
    )


class OtherQuestion(DecisionQuestion[NoulAnswer]):
    answer_type = NoulAnswer


class OtherVendorSchema(DecisionSchema, abstract=True):
    _question_type = OtherQuestion


class Other(OtherVendorSchema):
    q = OtherQuestion(instructions="x")


jev = rt.decisions.TypeSafeAI(model_name="jev-latest")


def schema_access(triage: Triage) -> None:
    assert_type(Triage.is_urgent, NoulQuestion)
    assert_type(Triage.department, ChoiceQuestion)
    assert_type(Triage.frustration, ScoreQuestion)

    assert_type(triage.is_urgent, NoulAnswer)
    assert_type(triage.department, ChoiceAnswer)
    assert_type(triage.frustration, ScoreAnswer)

    assert_type(triage.is_urgent.noul, float)
    assert_type(triage.department.probabilities, dict[str, float])
    assert_type(triage.frustration.probabilities, dict[int, float])

    triage.is_urgent.choice  # type: ignore[attr-defined]


async def direct_call() -> None:
    resp = await jev.aask("I was charged twice", Triage)
    assert_type(resp, DecisionResponse[Triage])
    assert_type(resp.structured.department, ChoiceAnswer)
    assert_type(resp.structured.is_urgent.noul, float)
    assert_type(resp.cost, float | None)

    await jev.aask({"subject": "Duplicate charge"}, Triage)
    await jev.aask("x", Other)  # type: ignore[type-var]


async def node_calls() -> None:
    triage_ticket = rt.decision_node("Triage Ticket", model=jev, schema=Triage)
    result = await rt.call(triage_ticket, "I was charged twice")
    assert_type(result, DecisionResponse[Triage])
    assert_type(result.structured.frustration, ScoreAnswer)

    await rt.call(triage_ticket, state="I was charged twice")
    await rt.call(triage_ticket, {"subject": "Duplicate charge"})

    flow = rt.Flow(name="Ticket Triage", entry_point=triage_ticket)
    assert_type(flow.invoke("x").structured.is_urgent, NoulAnswer)

    rt.agent_node(
        "Support", llm=rt.llm.OpenAILLM("gpt-5.4-mini"), tool_nodes=[triage_ticket]
    )


async def other_hosts() -> None:
    openrouter = rt.decisions.OpenRouterAI("typesafe/jev-1.13")
    laya = rt.decisions.LayaAI("english", api_base="http://localhost:8000")
    assert_type(await openrouter.aask("x", Triage), DecisionResponse[Triage])

    via_laya = rt.decision_node("Triage via Laya", model=laya, schema=Triage)
    assert_type(await rt.call(via_laya, "x"), DecisionResponse[Triage])


def vendor_mismatch() -> None:
    rt.decision_node("Mismatch", model=jev, schema=Other)  # type: ignore[type-var]
