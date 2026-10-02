"""TypeSafe's System One question types (Noul, Choice, Score) and their answers.

Wire format: https://docs.typesafe.ai/api and the primitive pages under
https://docs.typesafe.ai/primitives/.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar, Literal, TypeVar

from typing_extensions import TypedDict

from railtracks.exceptions import NodeCreationError

from .._base import DecisionAnswer, DecisionQuestion, DecisionSchema

MAX_CHOICE_LABELS = 255
MIN_SCORE_LEVELS = 2
MAX_SCORE_LEVELS = 10

QuestionKind = Literal["noul", "choice", "score"]


# ================= Answers =================


class NoulAnswer(DecisionAnswer):
    """A yes/no answer.

    Attributes:
        noul: The probability of yes, from 0 to 1.
    """

    noul: float

    def __str__(self) -> str:
        return f"{'yes' if self.noul >= 0.5 else 'no'} {self.noul:.2f}"


class ChoiceAnswer(DecisionAnswer):
    """The most likely label and the probability of each label.

    Attributes:
        choice: The label with the highest probability.
        confidence: How concentrated the probabilities are, from 0 to 1.
        probabilities: The probability of each label.
    """

    choice: str
    confidence: float
    probabilities: dict[str, float]

    def __str__(self) -> str:
        probability = self.probabilities.get(self.choice, self.confidence)
        return f"{self.choice} {probability:.2f}"


class ScoreAnswer(DecisionAnswer):
    """An expected level on an ordered rubric.

    Attributes:
        score: The probability-weighted level; may fall between levels.
        confidence: Confidence in the score, from 0 to 1.
        probabilities: The probability of each level, keyed by level index.
        legend: The rubric's level descriptions, keyed by level index.
    """

    score: float
    confidence: float
    probabilities: dict[int, float]
    legend: dict[int, str]

    def __str__(self) -> str:
        return f"{self.score:.1f}/{max(self.legend)}"


# ================= Questions =================

_TAnswer = TypeVar("_TAnswer", bound=DecisionAnswer)


class NoulCriteria(TypedDict, total=False):
    """Optional descriptions of what counts as yes (``true``) and no (``false``)."""

    true: str
    false: str


def _require_text(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NodeCreationError(
            message=f"{what} must be a non-empty string, got {value!r}."
        )
    return value


class TypeSafeQuestion(DecisionQuestion[_TAnswer]):
    """Base for TypeSafe questions: a ``kind`` (the wire ``type``) and instructions."""

    kind: ClassVar[QuestionKind]

    def __init__(self, instructions: str) -> None:
        super().__init__()
        self.instructions = _require_text(instructions, "Question instructions")


class NoulQuestion(TypeSafeQuestion[NoulAnswer]):
    """A yes/no question, answered with the probability of yes."""

    kind = "noul"
    answer_type = NoulAnswer

    def __init__(
        self, *, instructions: str, criteria: NoulCriteria | None = None
    ) -> None:
        """Create a yes/no question.

        Args:
            instructions: The yes/no question or statement to evaluate.
            criteria: Optional descriptions of what counts as yes (``true``) and no
                (``false``).

        Raises:
            NodeCreationError: If the instructions or criteria are invalid.
        """
        super().__init__(instructions)
        if criteria is not None:
            unknown = set(criteria) - {"true", "false"}
            if unknown:
                raise NodeCreationError(
                    message=f"Noul criteria accepts only 'true' and 'false', got {sorted(unknown)}."
                )
            for key, description in criteria.items():
                _require_text(description, f"Noul criteria {key!r}")
        self.criteria: NoulCriteria | None = (
            NoulCriteria(**criteria) if criteria is not None else None
        )


class ChoiceQuestion(TypeSafeQuestion[ChoiceAnswer]):
    """Pick one of several named labels, answered with a probability per label."""

    kind = "choice"
    answer_type = ChoiceAnswer

    def __init__(self, *, instructions: str, criteria: Mapping[str, str]) -> None:
        """Create a choice question.

        Args:
            instructions: What the model should decide.
            criteria: Each label mapped to a description of when it applies
                (2 to 255 labels).

        Raises:
            NodeCreationError: If the instructions or criteria are invalid.
        """
        super().__init__(instructions)
        if not isinstance(criteria, Mapping):
            raise NodeCreationError(
                message=f"Choice criteria must be a mapping of label to description, got {type(criteria).__name__}."
            )
        if not 2 <= len(criteria) <= MAX_CHOICE_LABELS:
            raise NodeCreationError(
                message=f"Choice criteria must have at least 2 and at most {MAX_CHOICE_LABELS} labels, got {len(criteria)}."
            )
        for label, description in criteria.items():
            _require_text(label, "Choice label")
            _require_text(description, f"Description for choice label {label!r}")
        self.criteria: dict[str, str] = dict(criteria)


class ScoreQuestion(TypeSafeQuestion[ScoreAnswer]):
    """Rate on an ordered rubric, answered with the expected level."""

    kind = "score"
    answer_type = ScoreAnswer

    def __init__(self, *, instructions: str, criteria: Sequence[str]) -> None:
        """Create a score question.

        Args:
            instructions: What the model should rate.
            criteria: Ordered level descriptions; a level's index is its score
                (2 to 10 levels).

        Raises:
            NodeCreationError: If the instructions or criteria are invalid.
        """
        super().__init__(instructions)
        if isinstance(criteria, str) or not isinstance(criteria, Sequence):
            raise NodeCreationError(
                message=f"Score criteria must be a list of level descriptions, got {type(criteria).__name__}."
            )
        if not MIN_SCORE_LEVELS <= len(criteria) <= MAX_SCORE_LEVELS:
            raise NodeCreationError(
                message=f"Score criteria must have between {MIN_SCORE_LEVELS} and {MAX_SCORE_LEVELS} levels, got {len(criteria)}."
            )
        for index, description in enumerate(criteria):
            _require_text(description, f"Score level {index}")
        self.criteria: list[str] = list(criteria)


# ================= Schema =================


class TypeSafeSchema(DecisionSchema, abstract=True):
    """A set of TypeSafe questions, answered together in one request.

    Subclass it and declare each question as an attribute; the attribute name is the
    question's name::

        class Triage(TypeSafeSchema):
            is_urgent = TypeSafeSchema.Noul(instructions="The message conveys urgency")

    On an answered instance, each attribute is that question's answer.
    """

    _question_type = TypeSafeQuestion

    Noul = NoulQuestion
    Choice = ChoiceQuestion
    Score = ScoreQuestion
