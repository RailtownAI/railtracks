"""Vendor-neutral bases for System One (S1) decision models.

A vendor subclasses ``DecisionSchema`` (with ``abstract=True``) to provide its question
types, ``DecisionQuestion`` for each question and ``DecisionAnswer`` for each answer.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar, Generic, TypeVar, cast, overload

from pydantic import BaseModel, ConfigDict
from typing_extensions import Self

from railtracks.exceptions import NodeCreationError

_TAnswer = TypeVar("_TAnswer", bound="DecisionAnswer")


class DecisionAnswer(BaseModel):
    """One question's answer. ``str()`` is the compact summary an agent reads."""

    model_config = ConfigDict(frozen=True)


class DecisionQuestion(Generic[_TAnswer]):
    """A question declared as a ``DecisionSchema`` attribute.

    Class access returns the question; instance access returns its answer.
    """

    answer_type: ClassVar[type[DecisionAnswer]]

    def __init__(self) -> None:
        self._name: str | None = None
        self._bound_names: list[str] = []

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name
        self._bound_names.append(name)

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


class DecisionSchema:
    """Base for a set of questions answered together in one decision request.

    Subclasses declare questions as class attributes, collected in definition order
    (parents first) into ``__questions__``. An instance holds one answer per question.
    """

    __questions__: ClassVar[Mapping[str, DecisionQuestion[Any]]] = MappingProxyType({})
    _question_type: ClassVar[type[DecisionQuestion[Any]]] = DecisionQuestion
    _is_abstract_schema: ClassVar[bool] = True

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
                raise NodeCreationError(
                    message=f"Question name {attr!r} on {cls.__name__} clashes with an attribute of {cls.__mro__[1].__name__}.",
                    notes=["Rename the question; its attribute name is its name."],
                )
            if len(value._bound_names) > 1:
                raise NodeCreationError(
                    message=f"The same question object is used for more than one attribute of {cls.__name__}: {value._bound_names}.",
                    notes=["Create a separate question for each attribute."],
                )
            if not isinstance(value, cls._question_type):
                raise NodeCreationError(
                    message=f"Question {attr!r} on {cls.__name__} is a {type(value).__name__}, not a {cls._question_type.__name__}.",
                )
            questions[attr] = value

        if not questions:
            raise NodeCreationError(
                message=f"Schema {cls.__name__} has no questions.",
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
