"""Static cases for decision typing, checked by mypy in ``test_typing.py``.

Never executed. ``# type: ignore[...]`` lines are negative cases: mypy runs with
``--warn-unused-ignores``, so an ignore that stops being needed fails the check.
"""

from __future__ import annotations

import railtracks as rt
from railtracks.built_nodes.decisions import DecisionResponse
from railtracks.decisions import (
    ChoiceAnswer,
    DecisionAnswer,
    DecisionAnswers,
    DecisionSchema,
    DecisionState,
    PredicateAnswer,
    ScoreAnswer,
)
from railtracks.decisions.schema import (
    ChoiceQuestion,
    PredicateQuestion,
    ScoreQuestion,
)
from typing_extensions import assert_type

is_urgent = rt.decisions.Predicate(
    name="is_urgent", instructions="The message conveys urgency"
)
department = rt.decisions.Choice(
    name="department",
    instructions="Which team",
    choices={"billing": "Money", "technical": "Bugs"},
)
frustration = rt.decisions.Score(
    name="frustration", instructions="How frustrated", levels=["Calm", "Angry"]
)
needs_manager = rt.decisions.Noul(
    name="needs_manager", instructions="A manager must step in"
)

triage = DecisionSchema(predicate=[is_urgent], choice=[department], score=[frustration])

jev = rt.decisions.TypeSafeAI(model_name="jev-latest")


def questions() -> None:
    assert_type(is_urgent, PredicateQuestion)
    assert_type(department, ChoiceQuestion)
    assert_type(frustration, ScoreQuestion)
    assert_type(needs_manager, PredicateQuestion)
    assert_type(is_urgent.name, str)


def wrong_kind_in_a_list() -> None:
    DecisionSchema(predicate=[department])  # type: ignore[list-item]
    DecisionSchema(score=[is_urgent])  # type: ignore[list-item]
    rt.decisions.Predicate(instructions="x")  # type: ignore[call-arg]
    DecisionSchema([is_urgent])  # type: ignore[misc]


def answer_access(answers: DecisionAnswers) -> None:
    assert_type(answers[is_urgent], PredicateAnswer)
    assert_type(answers[department], ChoiceAnswer)
    assert_type(answers[frustration], ScoreAnswer)
    assert_type(answers[needs_manager], PredicateAnswer)
    assert_type(answers["is_urgent"], DecisionAnswer)

    assert_type(answers[is_urgent].probability, float)
    assert_type(answers[department].probabilities, dict[str, float])
    assert_type(answers[frustration].probabilities, dict[int, float])

    answers[is_urgent].choice  # type: ignore[attr-defined]
    answers.is_urgent  # type: ignore[attr-defined]


async def direct_call() -> None:
    resp = await jev.aask("I was charged twice", triage)
    assert_type(resp, DecisionResponse)
    assert_type(resp.structured, DecisionAnswers)
    assert_type(resp.structured[department], ChoiceAnswer)
    assert_type(resp.cost, float | None)

    await jev.aask({"subject": "Duplicate charge"}, triage)
    await jev.aask(DecisionState(text="x", attachments=["a.png"]), triage)
    await jev.aask("x", DecisionSchema)  # type: ignore[arg-type]


async def node_calls() -> None:
    triage_ticket = rt.decision_node("Triage Ticket", model=jev, schema=triage)
    result = await rt.call(triage_ticket, "I was charged twice")
    assert_type(result, DecisionResponse)
    assert_type(result.structured[frustration], ScoreAnswer)

    await rt.call(triage_ticket, state="I was charged twice")
    await rt.call(triage_ticket, {"subject": "Duplicate charge"})
    await rt.call(triage_ticket, DecisionState(attachments="cat.png"))

    flow = rt.Flow(name="Ticket Triage", entry_point=triage_ticket)
    assert_type(flow.invoke("x").structured[is_urgent], PredicateAnswer)

    rt.agent_node(
        "Support", llm=rt.llm.OpenAILLM("gpt-5.4-mini"), tool_nodes=[triage_ticket]
    )


async def other_providers() -> None:
    openrouter = rt.decisions.OpenRouterAI("typesafe/jev-1.13")
    luna = rt.decisions.OpenAIDecisions("gpt-6-luna")
    assert_type(await openrouter.aask("x", triage), DecisionResponse)
    assert_type(await luna.aask("x", triage), DecisionResponse)


def not_a_schema() -> None:
    rt.decision_node("Mismatch", model=jev, schema=DecisionSchema)  # type: ignore[arg-type]


def not_a_decision_model() -> None:
    chat = rt.llm.OpenAILLM("gpt-5.4-mini")
    rt.decision_node("Chat", model=chat, schema=triage)  # type: ignore[arg-type]
