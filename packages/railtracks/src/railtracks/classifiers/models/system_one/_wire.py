"""TypeSafe ``/v1/systemone`` request bodies and response parsing.

Shapes follow https://docs.typesafe.ai/api: questions and answers are keyed by
question name, and every answer carries its question's ``type``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import ValidationError

from ..._exceptions import ClassifierRequestError, ClassifierResponseError
from ...model import DecisionReply
from ...schema import DecisionAnswer, DecisionSchema, DecisionState
from .schema import TypeSafeQuestion, TypeSafeSchema

_TSchema = TypeVar("_TSchema", bound=DecisionSchema)


def typesafe_questions(
    schema: type[DecisionSchema],
) -> Mapping[str, TypeSafeQuestion[Any]]:
    """``schema``'s questions, once it is confirmed to be in this format.

    Raises:
        ClassifierRequestError: If ``schema`` is not a ``TypeSafeSchema`` subclass.
    """
    if not issubclass(schema, TypeSafeSchema):
        raise ClassifierRequestError(
            f"{schema.__name__} is not a TypeSafeSchema; /v1/systemone hosts only "
            "answer TypeSafeSchema questions."
        )
    return schema.__questions__


def question_to_wire(question: TypeSafeQuestion[Any]) -> dict[str, Any]:
    """One question in its wire form (``type``, ``instructions``, ``criteria``)."""
    wire: dict[str, Any] = {
        "type": question.kind,
        "instructions": question.instructions,
    }
    criteria = getattr(question, "criteria", None)
    if criteria is not None:
        wire["criteria"] = criteria
    return wire


def questions_to_wire(schema: type[DecisionSchema]) -> dict[str, dict[str, Any]]:
    """Every question of ``schema`` in wire form, keyed by name in definition order."""
    return {
        name: question_to_wire(question)
        for name, question in typesafe_questions(schema).items()
    }


def build_request(
    model_name: str, state: DecisionState, schema: type[DecisionSchema]
) -> dict[str, Any]:
    """The JSON body for ``POST /v1/systemone``."""
    return {"state": state, "model": model_name, "questions": questions_to_wire(schema)}


def _malformed(field: str, problem: str = "missing") -> ClassifierResponseError:
    return ClassifierResponseError(
        f"Malformed decision response: {problem} field {field!r}",
        notes=["Check that api_base points at a /v1/systemone-compatible server."],
    )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_cost(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


def parse_response(body: object, schema: type[_TSchema]) -> DecisionReply[_TSchema]:
    """Parse a ``/v1/systemone`` JSON body into a ``schema`` instance and metadata.

    Raises:
        ClassifierResponseError: If the body is not an object, or an answer for one of
            ``schema``'s questions is missing or malformed. The message names the field.
    """
    if not isinstance(body, dict):
        raise _malformed("<body>", "expected a JSON object for")
    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise _malformed("answers")

    parsed: dict[str, DecisionAnswer] = {}
    for name, question in typesafe_questions(schema).items():
        raw = answers.get(name)
        if not isinstance(raw, dict):
            raise _malformed(f"answers.{name}")
        if raw.get("type") != question.kind:
            raise _malformed(f"answers.{name}.type", f"expected {question.kind!r} for")
        try:
            parsed[name] = question.answer_type.model_validate(raw)
        except ValidationError as e:
            error = e.errors(include_url=False)[0]
            location = ".".join(str(part) for part in error["loc"])
            problem = "missing" if error["type"] == "missing" else "invalid"
            raise _malformed(f"answers.{name}.{location}", problem) from e

    usage = body.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    model = body.get("model")
    provider = body.get("provider")
    return DecisionReply(
        structured=schema(parsed),
        reported_model_name=model if isinstance(model, str) else None,
        provider=provider if isinstance(provider, str) else None,
        input_tokens=_optional_int(usage.get("input_tokens")),
        output_tokens=_optional_int(usage.get("output_tokens")),
        reported_cost=_optional_cost(usage.get("cost")),
        raw=body,
    )
