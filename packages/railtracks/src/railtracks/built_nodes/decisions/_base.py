"""Vendor-neutral bases for System One (S1) decision models.

A vendor subclasses ``DecisionSchema`` (with ``abstract=True``) to provide its question
types, ``DecisionQuestion`` for each question and ``DecisionAnswer`` for each answer,
and ``DecisionModel`` for the client. ``DecisionModel._ask`` holds what every vendor
shares: ``decision.*`` events, retries, timing and pricing.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar, Generic, TypeVar, Union, cast, overload

from pydantic import BaseModel, ConfigDict
from typing_extensions import Self, TypeAlias

from railtracks.context.central import get_current_scope, is_context_active
from railtracks.events._resolve import has_enclosing_node
from railtracks.events.decision import (
    DecisionFailureEvent,
    DecisionInvocationEvent,
    DecisionResponseEvent,
)
from railtracks.events.send import emit
from railtracks.exceptions import (
    DecisionRateLimitError,
    DecisionServerError,
    DecisionTimeoutError,
    NodeCreationError,
)
from railtracks.llm._exceptions import RetryError
from railtracks.llm.retries import RetryApproach

from .pricing import decision_cost
from .response import DecisionResponse

_TAnswer = TypeVar("_TAnswer", bound="DecisionAnswer")
_TSchema = TypeVar("_TSchema", bound="DecisionSchema")
_TVendorSchema = TypeVar("_TVendorSchema", bound="DecisionSchema")

DecisionState: TypeAlias = Union[str, dict[str, Any], list[Any]]
"""What a decision is about: text, or a JSON object or array."""

RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    DecisionRateLimitError,
    DecisionServerError,
    DecisionTimeoutError,
)


class DecisionAnswer(BaseModel):
    """One question's answer. ``str()`` is the compact summary an agent reads."""

    model_config = ConfigDict(frozen=True)


class DecisionQuestion(Generic[_TAnswer]):
    """A question declared as a ``DecisionSchema`` attribute.

    Class access returns the question; instance access returns its answer.
    """

    answer_type: ClassVar[type[DecisionAnswer]]

    def __init__(self, instructions: str) -> None:
        if not isinstance(instructions, str) or not instructions.strip():
            raise NodeCreationError(
                message=f"Question instructions must be a non-empty string, got {instructions!r}."
            )
        self.instructions = instructions
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


@dataclass(frozen=True)
class DecisionReply(Generic[_TSchema]):
    """What a vendor's transport returns for one successful request."""

    structured: _TSchema
    reported_model_name: str | None
    provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    raw: dict[str, Any]


class DecisionModel(ABC, Generic[_TVendorSchema]):
    """Base for a System One model client, generic in the vendor's schema base."""

    schema_base: ClassVar[type[DecisionSchema]]

    def __init__(
        self,
        model_name: str,
        *,
        api_base: str,
        retry_approach: RetryApproach | None = None,
    ) -> None:
        self.model_name = model_name
        self.api_base = api_base
        self.retry_approach = retry_approach

    @abstractmethod
    async def aask(
        self, state: DecisionState, schema: type[_TVendorSchema]
    ) -> DecisionResponse[_TVendorSchema]:
        """Answer every question in ``schema`` about ``state`` in one request."""

    @abstractmethod
    async def _send(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
        """Make one request, raising a ``DecisionModelError`` on failure."""

    @abstractmethod
    def _pricing_keys(self) -> list[str]:
        """The ``litellm.model_cost`` keys to try for this model, in order."""

    @abstractmethod
    def _describe_questions(self, schema: type[_TSchema]) -> dict[str, Any]:
        """``schema``'s questions as plain JSON, for the invocation event."""

    async def _ask(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionResponse[_TSchema]:
        # outside a node (a plain script, or a Session body) there is no parent to
        # resolve, and emitting would only log an error
        observed = is_context_active() and has_enclosing_node(get_current_scope())
        decision_id = str(uuid.uuid4())
        if observed:
            await emit(
                DecisionInvocationEvent(
                    decision_id=decision_id,
                    model_name=self.model_name,
                    api_base=self.api_base,
                    state=state,
                    questions=self._describe_questions(schema),
                )
            )

        start = time.perf_counter()
        try:
            reply = await self._send_with_retries(state, schema)
        except Exception as e:
            if observed:
                await emit(
                    DecisionFailureEvent.from_exception(
                        e, decision_id=decision_id, model_name=self.model_name
                    )
                )
            raise
        latency = time.perf_counter() - start

        response = DecisionResponse(
            structured=reply.structured,
            model_name=reply.reported_model_name or self.model_name,
            provider=reply.provider,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            latency=latency,
            cost=decision_cost(
                self._pricing_keys(), reply.input_tokens, reply.output_tokens
            ),
            raw=reply.raw,
        )
        if observed:
            await emit(
                DecisionResponseEvent(
                    decision_id=decision_id,
                    model_name=self.model_name,
                    reported_model_name=reply.reported_model_name,
                    provider=reply.provider,
                    answers=response.structured.encode(),
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    total_cost=response.cost,
                    latency=latency,
                )
            )
        return response

    async def _send_with_retries(
        self, state: DecisionState, schema: type[_TSchema]
    ) -> DecisionReply[_TSchema]:
        if self.retry_approach is None:
            return await self._send(state, schema)
        try:
            return await self.retry_approach.acall_with_retry(
                lambda: self._send(state, schema), retry_on=RETRYABLE_ERRORS
            )
        except RetryError as e:
            # surface the decision error itself, not the LLM-flavoured RetryError
            raise e.exception_list[-1] from e
