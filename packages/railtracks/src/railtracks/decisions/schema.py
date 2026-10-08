"""Decision schemas: the questions a decision model answers together, and their answers.

Users create named ``Predicate`` (alias ``Noul``), ``Choice`` and ``Score`` questions
and group them in a ``DecisionSchema``. Each question type has a typed answer
(``PredicateAnswer``, ``ChoiceAnswer``, ``ScoreAnswer``), which ``DecisionAnswers``
returns when indexed with that question.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from types import MappingProxyType
from typing import Any, ClassVar, Generic, Literal, TypeVar, overload

from pydantic import BaseModel, ConfigDict

from ._exceptions import SchemaDefinitionError

_TAnswer = TypeVar("_TAnswer", bound="DecisionAnswer")

QuestionKind = Literal["predicate", "choice", "score"]

MAX_CHOICES = 255
MAX_SCORE_LEVELS = 10


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


def _non_blank(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaDefinitionError(
            f"Question {what} must be a non-empty string, got {value!r}."
        )
    return value


class DecisionQuestion(Generic[_TAnswer]):
    """A named question; indexing ``DecisionAnswers`` with it returns its answer."""

    kind: ClassVar[QuestionKind]
    """The wire ``type``."""
    answer_type: ClassVar[type[DecisionAnswer]]

    def __init__(self, name: str, instructions: str) -> None:
        self._name = _non_blank(name, "name")
        self.instructions = _non_blank(instructions, "instructions")

    @property
    def name(self) -> str:
        """The question's name; answers are keyed by it."""
        return self._name

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self._name!r})"


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

    def __init__(self, *, name: str, instructions: str) -> None:
        """Create a predicate question.

        Args:
            name: The question's name, unique within a schema.
            instructions: The condition to evaluate, phrased so that "true" means yes.

        Raises:
            SchemaDefinitionError: If the name or instructions are blank.
        """
        super().__init__(name, instructions)


class ChoiceQuestion(DecisionQuestion[ChoiceAnswer]):
    """Pick one of several values, answered with a probability per value."""

    kind: ClassVar[QuestionKind] = "choice"
    answer_type = ChoiceAnswer

    def __init__(
        self,
        *,
        name: str,
        instructions: str,
        choices: Mapping[str, str] | Sequence[str],
    ) -> None:
        """Create a choice question.

        Args:
            name: The question's name, unique within a schema.
            instructions: What the model should decide.
            choices: The values to pick from, as a list, or a mapping of value to a
                description of when it applies (2 to 255 values).

        Raises:
            SchemaDefinitionError: If the name, instructions or choices are invalid.
        """
        super().__init__(name, instructions)
        self.choices = _options(choices, "Choice values", MAX_CHOICES)


class ScoreQuestion(DecisionQuestion[ScoreAnswer]):
    """Rate against ordered levels, answered with the expected level."""

    kind: ClassVar[QuestionKind] = "score"
    answer_type = ScoreAnswer

    def __init__(
        self,
        *,
        name: str,
        instructions: str,
        levels: Mapping[str, str] | Sequence[str],
    ) -> None:
        """Create a score question.

        Args:
            name: The question's name, unique within a schema.
            instructions: What the model should rate.
            levels: The level labels from lowest to highest, as a list, or a mapping of
                label to the level's criteria (2 to 10 levels). A level's index is its
                score.

        Raises:
            SchemaDefinitionError: If the name, instructions or levels are invalid.
        """
        super().__init__(name, instructions)
        self.levels = _options(levels, "Score levels", MAX_SCORE_LEVELS)


Predicate = PredicateQuestion
Noul = PredicateQuestion
"""An alias of ``Predicate``."""
Choice = ChoiceQuestion
Score = ScoreQuestion


# ================= Schema =================


class DecisionSchema:
    """The questions answered together in one decision request::

        is_urgent = Predicate(name="is_urgent", instructions="The message is urgent")
        team = Choice(
            name="team",
            instructions="Which team should handle this",
            choices={"billing": "Payments and refunds", "technical": "Bugs"},
        )
        triage = DecisionSchema(predicate=[is_urgent], choice=[team])

    Questions are ordered predicates first, then choices, then scores, each in list
    order. A question object can be shared by several schemas.
    """

    _KINDS: ClassVar[tuple[tuple[str, type[DecisionQuestion[Any]]], ...]] = (
        ("predicate", PredicateQuestion),
        ("choice", ChoiceQuestion),
        ("score", ScoreQuestion),
    )

    def __init__(
        self,
        *,
        predicate: Sequence[PredicateQuestion] = (),
        choice: Sequence[ChoiceQuestion] = (),
        score: Sequence[ScoreQuestion] = (),
    ) -> None:
        """Group questions into a schema.

        Args:
            predicate: Yes/no questions (``Predicate`` or ``Noul``).
            choice: ``Choice`` questions.
            score: ``Score`` questions.

        Raises:
            SchemaDefinitionError: If a list holds a question of another kind, two
                questions share a name, or there are no questions.
        """
        given = {"predicate": predicate, "choice": choice, "score": score}
        questions: dict[str, DecisionQuestion[Any]] = {}
        for kind, question_type in self._KINDS:
            values = given[kind]
            if not isinstance(values, (list, tuple)):
                raise SchemaDefinitionError(
                    f"{kind}= must be a list of {question_type.__name__}, "
                    f"got {type(values).__name__}."
                )
            for question in values:
                if not isinstance(question, question_type):
                    raise SchemaDefinitionError(
                        f"{kind}= holds a {type(question).__name__}, "
                        f"not a {question_type.__name__}.",
                    )
                if question.name in questions:
                    raise SchemaDefinitionError(
                        f"Two questions are named {question.name!r}.",
                        notes=["Question names must be unique within a schema."],
                    )
                questions[question.name] = question
        if not questions:
            raise SchemaDefinitionError(
                "The schema has no questions.",
                notes=["Pass at least one question in predicate=, choice= or score=."],
            )
        self._questions = MappingProxyType(questions)

    @property
    def questions(self) -> Mapping[str, DecisionQuestion[Any]]:
        """Every question keyed by name, in schema order."""
        return self._questions

    def __repr__(self) -> str:
        groups = ", ".join(
            f"{kind}={[q.name for q in self._questions.values() if q.kind == kind]}"
            for kind, _ in self._KINDS
        )
        return f"DecisionSchema({groups})"


class DecisionAnswers(Mapping[str, DecisionAnswer]):
    """One answer per question of a schema.

    Index with a question to get its typed answer (``answers[is_urgent]`` is a
    ``PredicateAnswer``), or with a name to get it untyped. Iterates over the question
    names in schema order.
    """

    def __init__(
        self, schema: DecisionSchema, answers: Mapping[str, DecisionAnswer]
    ) -> None:
        """Hold one answer per question.

        Args:
            schema: The schema the answers are for.
            answers: The answers keyed by question name.

        Raises:
            ValueError: If an answer is missing, unexpected, or of the wrong type.
        """
        questions = schema.questions
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
        self._schema = schema
        self._answers = {name: answers[name] for name in questions}

    @property
    def schema(self) -> DecisionSchema:
        """The schema these answers are for."""
        return self._schema

    @overload
    def __getitem__(self, key: DecisionQuestion[_TAnswer]) -> _TAnswer: ...

    @overload
    def __getitem__(self, key: str) -> DecisionAnswer: ...

    def __getitem__(self, key: DecisionQuestion[Any] | str) -> DecisionAnswer:
        if isinstance(key, DecisionQuestion):
            # a same-named question from another schema is not this one
            if self._schema.questions.get(key.name) is not key:
                raise KeyError(key.name)
            key = key.name
        return self._answers[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._answers)

    def __len__(self) -> int:
        return len(self._answers)

    def encode(self) -> dict[str, Any]:
        """The answers as plain JSON values, in schema order."""
        return {
            name: answer.model_dump(mode="json")
            for name, answer in self._answers.items()
        }

    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={v!r}" for k, v in self._answers.items())
        return f"DecisionAnswers({fields})"
