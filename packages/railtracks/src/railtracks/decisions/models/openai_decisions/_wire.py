"""OpenAI ``/v1/decisions`` request bodies and response parsing.

Shapes follow https://developers.openai.com/api/docs/guides/decisions and the
``Decision`` types in ``openai`` 3.26: questions and answers are arrays carrying an
optional ``name``, choice and score probabilities are arrays of objects, and any answer
may be a ``refusal``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import ValidationError

from ..._exceptions import (
    DecisionProviderRefusalError,
    DecisionProviderRequestError,
    DecisionProviderResponseError,
)
from ...model import DecisionReply
from ...schema import DecisionAnswer, DecisionSchema, DecisionState
from .schema import (
    OpenAIChoiceQuestion,
    OpenAIQuestion,
    OpenAISchema,
    OpenAIScoreQuestion,
)

_TSchema = TypeVar("_TSchema", bound=DecisionSchema)


def openai_questions(
    schema: type[DecisionSchema],
) -> Mapping[str, OpenAIQuestion[Any]]:
    """``schema``'s questions, once it is confirmed to be an ``OpenAISchema``.

    Raises:
        DecisionProviderRequestError: If ``schema`` is not an ``OpenAISchema`` subclass.
    """
    if not issubclass(schema, OpenAISchema):
        raise DecisionProviderRequestError(
            f"{schema.__name__} is not an OpenAISchema; OpenAI's Decisions API only "
            "answers OpenAISchema questions."
        )
    return schema.__questions__


def _options_to_wire(
    options: Mapping[str, str | None], key: str
) -> list[dict[str, str]]:
    wire = []
    for name, description in options.items():
        item = {key: name}
        if description is not None:
            item["description"] = description
        wire.append(item)
    return wire


def question_to_wire(name: str, question: OpenAIQuestion[Any]) -> dict[str, Any]:
    """One question in its wire form (``type``, ``name``, ``instructions``, ...)."""
    wire: dict[str, Any] = {
        "type": question.kind,
        "name": name,
        "instructions": question.instructions,
    }
    if isinstance(question, OpenAIChoiceQuestion):
        wire["choices"] = _options_to_wire(question.choices, "value")
    elif isinstance(question, OpenAIScoreQuestion):
        wire["levels"] = _options_to_wire(question.levels, "label")
    return wire


def questions_to_wire(schema: type[DecisionSchema]) -> dict[str, dict[str, Any]]:
    """Every question of ``schema`` in wire form, keyed by name in definition order."""
    return {
        name: question_to_wire(name, question)
        for name, question in openai_questions(schema).items()
    }


def is_user_messages(state: DecisionState) -> bool:
    """Whether ``state`` is already OpenAI ``input`` messages (for text and images)."""
    return (
        isinstance(state, list)
        and bool(state)
        and all(isinstance(m, dict) and m.get("role") == "user" for m in state)
    )


def to_input(state: DecisionState) -> str | list[Any]:
    """The ``input`` field: text as is, user messages as is, other JSON as JSON text."""
    if isinstance(state, str):
        return state
    if isinstance(state, list) and is_user_messages(state):
        return state
    return json.dumps(state)


def build_request(
    model_name: str, state: DecisionState, schema: type[DecisionSchema]
) -> dict[str, Any]:
    """The JSON body for ``POST /v1/decisions``."""
    return {
        "model": model_name,
        "input": to_input(state),
        "questions": list(questions_to_wire(schema).values()),
    }


def _malformed(field: str, problem: str = "missing") -> DecisionProviderResponseError:
    return DecisionProviderResponseError(
        f"Malformed decision response: {problem} field {field!r}"
    )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _answer_payload(
    raw: dict[str, Any], question: OpenAIQuestion[Any]
) -> dict[str, Any]:
    """Reshape one wire answer into the fields of ``question.answer_type``."""
    if question.kind == "predicate":
        return {"probability": raw.get("probability")}
    probabilities = raw.get("probabilities")
    if not isinstance(probabilities, list) or not all(
        isinstance(p, dict) and "value" in p and "probability" in p
        for p in probabilities
    ):
        raise ValueError("probabilities")
    payload = {
        "confidence": raw.get("confidence"),
        "probabilities": {p["value"]: p["probability"] for p in probabilities},
    }
    if question.kind == "choice":
        payload["choice"] = raw.get("choice")
    else:
        payload["score"] = raw.get("score")
        payload["legend"] = {p["value"]: p.get("label") for p in probabilities}
    return payload


def _match_answers(answers: list[Any], names: list[str]) -> dict[str, object]:
    """Each question's raw answer: by ``name``, or by position if the host sent none."""
    by_name = {
        a["name"]: a
        for a in answers
        if isinstance(a, dict) and isinstance(a.get("name"), str)
    }
    if by_name:
        return {name: by_name.get(name) for name in names}
    return {
        name: answers[i] if i < len(answers) else None for i, name in enumerate(names)
    }


def _parse_answer(
    name: str, question: OpenAIQuestion[Any], raw: dict[str, Any]
) -> DecisionAnswer:
    if raw.get("type") != question.kind:
        raise _malformed(f"answers.{name}.type", f"expected {question.kind!r} for")
    try:
        return question.answer_type.model_validate(_answer_payload(raw, question))
    except ValidationError as e:
        error = e.errors(include_url=False)[0]
        location = ".".join(str(part) for part in error["loc"])
        problem = "missing" if error["input"] is None else "invalid"
        raise _malformed(f"answers.{name}.{location}", problem) from e
    except ValueError as e:
        raise _malformed(f"answers.{name}.{e}", "invalid") from e


def parse_response(body: object, schema: type[_TSchema]) -> DecisionReply[_TSchema]:
    """Parse a ``/v1/decisions`` JSON body into a ``schema`` instance and metadata.

    Answers are matched to questions by ``name``, or by position when the host leaves
    names out.

    Raises:
        DecisionProviderRefusalError: If the model declined any question; carries the
            answers it did give.
        DecisionProviderResponseError: If the body is not an object, or an answer for
            one of ``schema``'s questions is missing or malformed. The message names
            the field.
    """
    if not isinstance(body, dict):
        raise _malformed("<body>", "expected a JSON object for")
    answers = body.get("answers")
    if not isinstance(answers, list):
        raise _malformed("answers")

    questions = openai_questions(schema)
    matched = _match_answers(answers, list(questions))
    parsed: dict[str, DecisionAnswer] = {}
    refused: list[str] = []
    for name, question in questions.items():
        raw = matched[name]
        if not isinstance(raw, dict):
            raise _malformed(f"answers.{name}")
        if raw.get("type") == "refusal":
            refused.append(name)
        else:
            parsed[name] = _parse_answer(name, question, raw)

    if refused:
        raise DecisionProviderRefusalError(
            f"The model declined to answer: {', '.join(refused)}.",
            refused=refused,
            answers=parsed,
            notes=[
                "Rephrase the question or the input; retrying unchanged won't help."
            ],
        )

    usage = body.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    model = body.get("model")
    return DecisionReply(
        structured=schema(parsed),
        reported_model_name=model if isinstance(model, str) else None,
        provider=None,
        input_tokens=_optional_int(usage.get("input_tokens")),
        output_tokens=_optional_int(usage.get("output_tokens")),
        reported_cost=None,
        raw=body,
    )
