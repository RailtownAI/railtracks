"""Static cases for decision typing, checked by mypy in ``test_typing.py``.

Never executed. ``# type: ignore[...]`` lines are negative cases: mypy runs with
``--warn-unused-ignores``, so an ignore that stops being needed fails the check.
"""

from __future__ import annotations

from railtracks.built_nodes.decisions.typesafe.schema import (
    ChoiceAnswer,
    ChoiceQuestion,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
    TypeSafeSchema,
)
from typing_extensions import assert_type


class Triage(TypeSafeSchema):
    is_urgent = TypeSafeSchema.Noul(instructions="The message conveys urgency")
    department = TypeSafeSchema.Choice(
        instructions="Which team", criteria={"billing": "Money", "technical": "Bugs"}
    )
    frustration = TypeSafeSchema.Score(
        instructions="How frustrated", criteria=["Calm", "Angry"]
    )


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
