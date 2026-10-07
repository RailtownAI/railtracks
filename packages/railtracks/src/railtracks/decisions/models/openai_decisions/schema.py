"""OpenAI's Decisions API question types (Predicate, Choice, Score) and their answers.

Wire format: https://developers.openai.com/api/docs/guides/decisions. Choice and Score
answers have the same fields as on ``/v1/systemone`` hosts, so they reuse
``ChoiceAnswer`` and ``ScoreAnswer``; only the predicate answer is new.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Literal, TypeVar

from ..._exceptions import SchemaDefinitionError
from ...schema import DecisionAnswer, DecisionQuestion, DecisionSchema
from ..typesafe_compatible.schema import ChoiceAnswer, ScoreAnswer

QuestionKind = Literal["predicate", "choice", "score"]

_TAnswer = TypeVar("_TAnswer", bound=DecisionAnswer)


class PredicateAnswer(DecisionAnswer):
    """The probability that a yes/no condition is true.

    Attributes:
        probability: The probability the condition is true, from 0 to 1.
    """

    probability: float

    def __str__(self) -> str:
        return f"{'yes' if self.probability >= 0.5 else 'no'} {self.probability:.2f}"


def _options(
    options: Mapping[str, str] | Sequence[str], what: str
) -> dict[str, str | None]:
    """Normalize choices or levels to ``{name: description or None}``, in order."""
    if isinstance(options, str) or not isinstance(options, (Mapping, Sequence)):
        raise SchemaDefinitionError(
            f"{what} must be a list of names or a mapping of name to description, "
            f"got {type(options).__name__}."
        )
    pairs: list[tuple[str, str | None]] = (
        list(options.items())
        if isinstance(options, Mapping)
        else [(name, None) for name in options]
    )
    names = [name for name, _ in pairs]
    if len(set(names)) != len(names):
        raise SchemaDefinitionError(f"{what} must be unique, got {names}.")
    if len(names) < 2:
        raise SchemaDefinitionError(
            f"{what} need at least 2 entries, got {len(names)}."
        )
    for name, description in pairs:
        if not isinstance(name, str) or not name.strip():
            raise SchemaDefinitionError(
                f"{what} must be non-empty strings, got {name!r}."
            )
        if description is not None and not isinstance(description, str):
            raise SchemaDefinitionError(
                f"The description for {name!r} must be a string, got {description!r}."
            )
    return dict(pairs)


class OpenAIQuestion(DecisionQuestion[_TAnswer]):
    """Base for OpenAI decision questions; ``kind`` is the wire ``type``."""

    kind: ClassVar[QuestionKind]


class PredicateQuestion(OpenAIQuestion[PredicateAnswer]):
    """Whether a condition holds, answered with its probability."""

    kind = "predicate"
    answer_type = PredicateAnswer

    def __init__(self, *, instructions: str) -> None:
        """Create a predicate question.

        Args:
            instructions: The condition to evaluate, phrased so that "true" means yes.

        Raises:
            SchemaDefinitionError: If the instructions are blank.
        """
        super().__init__(instructions)


class OpenAIChoiceQuestion(OpenAIQuestion[ChoiceAnswer]):
    """Pick one of several values, answered with a probability per value."""

    kind = "choice"
    answer_type = ChoiceAnswer

    def __init__(
        self, *, instructions: str, choices: Mapping[str, str] | Sequence[str]
    ) -> None:
        """Create a choice question.

        Args:
            instructions: What the model should decide.
            choices: The values to pick from, as a list, or a mapping of value to a
                description of when it applies (at least 2).

        Raises:
            SchemaDefinitionError: If the instructions or choices are invalid.
        """
        super().__init__(instructions)
        self.choices = _options(choices, "Choice values")


class OpenAIScoreQuestion(OpenAIQuestion[ScoreAnswer]):
    """Rate against ordered levels, answered with the expected level."""

    kind = "score"
    answer_type = ScoreAnswer

    def __init__(
        self, *, instructions: str, levels: Mapping[str, str] | Sequence[str]
    ) -> None:
        """Create a score question.

        Args:
            instructions: What the model should rate.
            levels: The level labels from lowest to highest, as a list, or a mapping of
                label to the level's criteria (at least 2). A level's index is its
                score.

        Raises:
            SchemaDefinitionError: If the instructions or levels are invalid.
        """
        super().__init__(instructions)
        self.levels = _options(levels, "Score levels")


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

    Predicate = PredicateQuestion
    Choice = OpenAIChoiceQuestion
    Score = OpenAIScoreQuestion
