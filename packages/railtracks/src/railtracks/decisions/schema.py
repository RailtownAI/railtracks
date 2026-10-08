"""Decision schemas: the questions a decision model answers together, and their answers.

Users subclass ``DecisionSchema`` and declare ``Predicate`` (alias ``Noul``), ``Choice``
and ``Score`` questions as class attributes. Each question type has a typed answer:
``PredicateAnswer``, ``ChoiceAnswer`` and ``ScoreAnswer``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any, ClassVar, Generic, Literal, TypeVar, Union, cast, overload

from pydantic import BaseModel, ConfigDict
from typing_extensions import Self, TypeAlias

from ._exceptions import SchemaDefinitionError

_TAnswer = TypeVar("_TAnswer", bound="DecisionAnswer")

QuestionKind = Literal["predicate", "choice", "score"]

MAX_CHOICES = 255
MAX_SCORE_LEVELS = 10

DecisionState: TypeAlias = Union[str, dict[str, Any], list[Any]]
"""What a decision is about: text, or a JSON object or array."""


# ================= Answers =================


class DecisionAnswer(BaseModel):
    """One question's answer. ``str()`` is the compact summary an agent reads."""

    model_config = ConfigDict(frozen=True)


class PredicateAnswer(DecisionAnswer):
    """The probability that a yes/no condition is true.

    Attributes:
        probability: The probability the condition is true, from 0 to 1.
    """

    probability: float

    def __str__(self) -> str:
        return f"{'yes' if self.probability >= 0.5 else 'no'} {self.probability:.2f}"


class ChoiceAnswer(DecisionAnswer):
    """The most likely value and the probability of each value.

    Attributes:
        choice: The value with the highest probability.
        confidence: How concentrated the probabilities are, from 0 to 1.
        probabilities: The probability of each value.
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


class DecisionQuestion(Generic[_TAnswer]):
    """A question declared as a ``DecisionSchema`` attribute.

    Class access returns the question; instance access returns its answer.
    """

    kind: ClassVar[QuestionKind]
    """The wire ``type``."""
    answer_type: ClassVar[type[DecisionAnswer]]

    def __init__(self, instructions: str) -> None:
        if not isinstance(instructions, str) or not instructions.strip():
            raise SchemaDefinitionError(
                f"Question instructions must be a non-empty string, got {instructions!r}."
            )
        self.instructions = instructions
        self._name: str | None = None
        self._bound_names: list[str] = []

    def __set_name__(self, owner: type, name: str) -> None:
        # the first binding keeps the name, so a schema that already uses this
        # question still works after a second one is rejected for reusing it
        if self._name is None:
            self._name = name
        self._bound_names.append(f"{owner.__name__}.{name}")

    @property
    def name(self) -> str:
        """The attribute name this question was declared under."""
        if self._name is None:
            raise AttributeError(
                f"{type(self).__name__} is not attached to a schema class"
            )
        return self._name

    @overload
    def __get__(self, instance: None, owner: type) -> Self: ...

    @overload
    def __get__(self, instance: DecisionSchema, owner: type) -> _TAnswer: ...

    def __get__(self, instance: DecisionSchema | None, owner: type) -> Self | _TAnswer:
        if instance is None:
            return self
        return cast(_TAnswer, instance._answers[self.name])


def _options(
    options: Mapping[str, str] | Sequence[str], what: str, most: int
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
    if not 2 <= len(pairs) <= most:
        raise SchemaDefinitionError(
            f"{what} need at least 2 and at most {most} entries, got {len(pairs)}."
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
    names = [name for name, _ in pairs]
    if len(set(names)) != len(names):
        raise SchemaDefinitionError(f"{what} must be unique, got {names}.")
    return dict(pairs)


class PredicateQuestion(DecisionQuestion[PredicateAnswer]):
    """Whether a condition holds, answered with its probability."""

    kind: ClassVar[QuestionKind] = "predicate"
    answer_type = PredicateAnswer

    def __init__(self, *, instructions: str) -> None:
        """Create a predicate question.

        Args:
            instructions: The condition to evaluate, phrased so that "true" means yes.

        Raises:
            SchemaDefinitionError: If the instructions are blank.
        """
        super().__init__(instructions)


class ChoiceQuestion(DecisionQuestion[ChoiceAnswer]):
    """Pick one of several values, answered with a probability per value."""

    kind: ClassVar[QuestionKind] = "choice"
    answer_type = ChoiceAnswer

    def __init__(
        self, *, instructions: str, choices: Mapping[str, str] | Sequence[str]
    ) -> None:
        """Create a choice question.

        Args:
            instructions: What the model should decide.
            choices: The values to pick from, as a list, or a mapping of value to a
                description of when it applies (2 to 255 values).

        Raises:
            SchemaDefinitionError: If the instructions or choices are invalid.
        """
        super().__init__(instructions)
        self.choices = _options(choices, "Choice values", MAX_CHOICES)


class ScoreQuestion(DecisionQuestion[ScoreAnswer]):
    """Rate against ordered levels, answered with the expected level."""

    kind: ClassVar[QuestionKind] = "score"
    answer_type = ScoreAnswer

    def __init__(
        self, *, instructions: str, levels: Mapping[str, str] | Sequence[str]
    ) -> None:
        """Create a score question.

        Args:
            instructions: What the model should rate.
            levels: The level labels from lowest to highest, as a list, or a mapping of
                label to the level's criteria (2 to 10 levels). A level's index is its
                score.

        Raises:
            SchemaDefinitionError: If the instructions or levels are invalid.
        """
        super().__init__(instructions)
        self.levels = _options(levels, "Score levels", MAX_SCORE_LEVELS)


# ================= Schema =================


class DecisionSchema:
    """A set of questions answered together in one decision request.

    Subclass it and declare each question as an attribute; the attribute name is the
    question's name::

        class Triage(DecisionSchema):
            is_urgent = DecisionSchema.Predicate(
                instructions="The message conveys urgency"
            )
            team = DecisionSchema.Choice(
                instructions="Which team should handle this",
                choices={"billing": "Payments and refunds", "technical": "Bugs"},
            )
            frustration = DecisionSchema.Score(
                instructions="How frustrated the customer is",
                levels=["Calm", "Annoyed", "Furious"],
            )

    Questions are collected in definition order (parents first) into ``__questions__``.
    ``Noul`` is an alias of ``Predicate``. On an answered instance, each attribute is
    that question's answer.
    """

    __questions__: ClassVar[Mapping[str, DecisionQuestion[Any]]] = MappingProxyType({})
    _question_type: ClassVar[type[DecisionQuestion[Any]]] = DecisionQuestion
    _is_abstract_schema: ClassVar[bool] = True

    Predicate = PredicateQuestion
    Noul = PredicateQuestion
    Choice = ChoiceQuestion
    Score = ScoreQuestion

    def __init_subclass__(cls, *, abstract: bool = False, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._is_abstract_schema = abstract
        if abstract:
            return

        reserved = {
            attr
            for base in cls.__mro__[1:]
            if base.__dict__.get("_is_abstract_schema", False)
            for attr in dir(base)
        }
        questions: dict[str, DecisionQuestion[Any]] = {}
        for base in reversed(cls.__mro__[1:]):
            questions.update(base.__dict__.get("__questions__", {}))

        for attr, value in cls.__dict__.items():
            if not isinstance(value, DecisionQuestion):
                continue
            if attr in reserved:
                raise SchemaDefinitionError(
                    f"Question name {attr!r} on {cls.__name__} clashes with an attribute of {cls.__mro__[1].__name__}.",
                    notes=["Rename the question; its attribute name is its name."],
                )
            if len(value._bound_names) > 1:
                raise SchemaDefinitionError(
                    f"The same question object is used for more than one attribute: {value._bound_names}.",
                    notes=["Create a separate question for each attribute."],
                )
            if not isinstance(value, cls._question_type):
                raise SchemaDefinitionError(
                    f"Question {attr!r} on {cls.__name__} is a {type(value).__name__}, not a {cls._question_type.__name__}.",
                )
            questions[attr] = value

        if not questions:
            raise SchemaDefinitionError(
                f"Schema {cls.__name__} has no questions.",
                notes=["Declare at least one question as a class attribute."],
            )
        cls.__questions__ = MappingProxyType(questions)

    def __init__(self, answers: Mapping[str, DecisionAnswer]) -> None:
        """Hold one answer per question.

        Args:
            answers: The answers keyed by question name.

        Raises:
            ValueError: If an answer is missing, unexpected, or of the wrong type.
        """
        questions = type(self).__questions__
        unexpected = set(answers) - set(questions)
        if unexpected:
            raise ValueError(f"Unexpected answers: {sorted(unexpected)}")
        for name, question in questions.items():
            if name not in answers:
                raise ValueError(f"Missing answer for question {name!r}")
            if not isinstance(answers[name], question.answer_type):
                raise ValueError(
                    f"Answer for question {name!r} must be a {question.answer_type.__name__}, got {type(answers[name]).__name__}"
                )
        self._answers = {name: answers[name] for name in questions}

    def encode(self) -> dict[str, Any]:
        """The answers as plain JSON values, in definition order."""
        return {
            name: answer.model_dump(mode="json")
            for name, answer in self._answers.items()
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DecisionSchema) or type(other) is not type(self):
            return NotImplemented
        return self._answers == other._answers

    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={v!r}" for k, v in self._answers.items())
        return f"{type(self).__name__}({fields})"
