"""TypeSafe's System One question types (Noul, Choice, Score) and their answers.

Wire format: https://docs.typesafe.ai/api and the primitive pages under
https://docs.typesafe.ai/primitives/.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Literal, TypeVar

from typing_extensions import TypedDict

from ..._exceptions import SchemaDefinitionError
from ...schema import (
    ChoiceAnswer,
    DecisionAnswer,
    DecisionQuestion,
    DecisionSchema,
    ScoreAnswer,
)

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


# ================= Questions =================

_TAnswer = TypeVar("_TAnswer", bound=DecisionAnswer)


class NoulCriteria(TypedDict, total=False):
    """Optional descriptions of what counts as yes (``true``) and no (``false``)."""

    true: str
    false: str


def _require_text(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaDefinitionError(
            f"{what} must be a non-empty string, got {value!r}."
        )
    return value


class TypeSafeQuestion(DecisionQuestion[_TAnswer]):
    """Base for TypeSafe questions; ``kind`` is the wire ``type``."""

    kind: ClassVar[QuestionKind]


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
            SchemaDefinitionError: If the instructions or criteria are invalid.
        """
        super().__init__(instructions)
        if criteria is not None:
            unknown = set(criteria) - {"true", "false"}
            if unknown:
                raise SchemaDefinitionError(
                    f"Noul criteria accepts only 'true' and 'false', got {sorted(unknown)}."
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
            SchemaDefinitionError: If the instructions or criteria are invalid.
        """
        super().__init__(instructions)
        if not isinstance(criteria, Mapping):
            raise SchemaDefinitionError(
                f"Choice criteria must be a mapping of label to description, got {type(criteria).__name__}."
            )
        if not 2 <= len(criteria) <= MAX_CHOICE_LABELS:
            raise SchemaDefinitionError(
                f"Choice criteria must have at least 2 and at most {MAX_CHOICE_LABELS} labels, got {len(criteria)}."
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
            SchemaDefinitionError: If the instructions or criteria are invalid.
        """
        super().__init__(instructions)
        if isinstance(criteria, str) or not isinstance(criteria, Sequence):
            raise SchemaDefinitionError(
                f"Score criteria must be a list of level descriptions, got {type(criteria).__name__}."
            )
        if not MIN_SCORE_LEVELS <= len(criteria) <= MAX_SCORE_LEVELS:
            raise SchemaDefinitionError(
                f"Score criteria must have between {MIN_SCORE_LEVELS} and {MAX_SCORE_LEVELS} levels, got {len(criteria)}."
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

    __questions__: ClassVar[Mapping[str, TypeSafeQuestion[Any]]]
    _question_type = TypeSafeQuestion

    Noul = NoulQuestion  # type: ignore[assignment]
    Choice = ChoiceQuestion  # type: ignore[assignment]
    Score = ScoreQuestion  # type: ignore[assignment]
