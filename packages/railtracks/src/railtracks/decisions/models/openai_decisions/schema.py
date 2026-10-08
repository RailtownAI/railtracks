"""OpenAI's Decisions API question types (Predicate, Choice, Score).

Wire format: https://developers.openai.com/api/docs/guides/decisions. The questions and
their validation are the generic ones from ``decisions/schema.py``; the subclasses here
only mark them as OpenAI questions so an ``OpenAISchema`` rejects other vendors' types.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, TypeVar

from ...schema import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionAnswer,
    DecisionQuestion,
    DecisionSchema,
    PredicateAnswer,
    PredicateQuestion,
    QuestionKind,
    ScoreAnswer,
    ScoreQuestion,
)

_TAnswer = TypeVar("_TAnswer", bound=DecisionAnswer)


class OpenAIQuestion(DecisionQuestion[_TAnswer]):
    """Base for OpenAI decision questions; ``kind`` is the wire ``type``."""

    kind: ClassVar[QuestionKind]


class OpenAIPredicateQuestion(PredicateQuestion, OpenAIQuestion[PredicateAnswer]):
    """Whether a condition holds, answered with its probability."""


class OpenAIChoiceQuestion(ChoiceQuestion, OpenAIQuestion[ChoiceAnswer]):
    """Pick one of several values, answered with a probability per value."""


class OpenAIScoreQuestion(ScoreQuestion, OpenAIQuestion[ScoreAnswer]):
    """Rate against ordered levels, answered with the expected level."""


class OpenAISchema(DecisionSchema, abstract=True):
    """A set of questions for OpenAI's Decisions API, answered together in one request.

    Subclass it and declare each question as an attribute; the attribute name is the
    question's name::

        class Triage(OpenAISchema):
            is_urgent = OpenAISchema.Predicate(
                instructions="The message conveys urgency"
            )

    On an answered instance, each attribute is that question's answer.
    """

    __questions__: ClassVar[Mapping[str, OpenAIQuestion[Any]]]
    _question_type = OpenAIQuestion

    Predicate = OpenAIPredicateQuestion
    Noul = OpenAIPredicateQuestion
    Choice = OpenAIChoiceQuestion
    Score = OpenAIScoreQuestion
