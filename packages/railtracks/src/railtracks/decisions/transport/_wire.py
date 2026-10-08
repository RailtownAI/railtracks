"""``DecisionSchema`` to and from the OpenAI-shape request ``litellm.adecisions`` takes.

rt always sends the OpenAI shape (``input`` plus a list of named ``questions``), for
every provider: litellm translates it per provider, keeps refusals (the System One
``state`` shape drops them) and accepts images where the provider does. Shapes follow
``litellm.types.decisions`` (1.104.2) and
https://developers.openai.com/api/docs/guides/decisions.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, TypeGuard

from pydantic import BaseModel, ValidationError

from .._exceptions import DecisionProviderRefusalError, DecisionProviderResponseError
from ..model import DecisionReply
from ..schema import (
    ChoiceQuestion,
    DecisionAnswer,
    DecisionAnswers,
    DecisionQuestion,
    DecisionSchema,
    ScoreQuestion,
)
from ..state import DecisionInput, DecisionState

# ================= Request =================


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


def question_to_wire(name: str, question: DecisionQuestion[Any]) -> dict[str, Any]:
    """One question in its wire form (``type``, ``name``, ``instructions``, ...)."""
    wire: dict[str, Any] = {
        "type": question.kind,
        "name": name,
        "instructions": question.instructions,
    }
    if isinstance(question, ChoiceQuestion):
        wire["choices"] = _options_to_wire(question.choices, "value")
    elif isinstance(question, ScoreQuestion):
        wire["levels"] = _options_to_wire(question.levels, "label")
    return wire


def describe_questions(schema: DecisionSchema) -> dict[str, dict[str, Any]]:
    """Every question of ``schema`` in wire form, keyed by name in definition order."""
    return {
        name: question_to_wire(name, question)
        for name, question in schema.questions.items()
    }


def questions_to_wire(schema: DecisionSchema) -> list[dict[str, Any]]:
    """The ``questions`` argument: every question in wire form, in definition order.

    Names are always sent and are unique (they are attribute names), so System One
    providers key their answers by name rather than by position.
    """
    return list(describe_questions(schema).values())


def is_user_messages(state: DecisionInput) -> TypeGuard[list[Any]]:
    """Whether ``state`` is already OpenAI ``input`` messages (for text and images)."""
    return (
        isinstance(state, list)
        and bool(state)
        and all(isinstance(m, dict) and m.get("role") == "user" for m in state)
    )


def to_input(state: DecisionInput) -> str | list[Any]:
    """The ``input`` argument: text as is, user messages as is, other JSON as JSON text."""
    if isinstance(state, str):
        return state
    if isinstance(state, DecisionState):
        return state.to_input()
    if is_user_messages(state):
        return state
    return json.dumps(state)


# ================= Response =================


def _malformed(field: str, problem: str = "missing") -> DecisionProviderResponseError:
    return DecisionProviderResponseError(
        f"Malformed decision response: {problem} field {field!r}"
    )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _answer_payload(
    raw: dict[str, Any], question: DecisionQuestion[Any]
) -> dict[str, Any]:
    """Reshape one wire answer into the fields of ``question.answer_type``."""
    if isinstance(question, (ChoiceQuestion, ScoreQuestion)):
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
        if isinstance(question, ChoiceQuestion):
            payload["choice"] = raw.get("choice")
        else:
            payload["score"] = raw.get("score")
            payload["legend"] = {p["value"]: p.get("label") for p in probabilities}
        return payload
    return {"probability": raw.get("probability")}


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
    name: str, question: DecisionQuestion[Any], raw: dict[str, Any]
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


def parse_response(response: object, schema: DecisionSchema) -> DecisionReply:
    """Parse an ``OpenAIDecisionResponse`` (or its JSON dict) into a ``schema`` instance.

    Answers are matched to questions by ``name``, or by position when the provider
    leaves names out. The cost is left to the caller, which reads it from litellm's
    hidden params.

    Raises:
        DecisionProviderRefusalError: If the model declined any question; carries the
            answers it did give.
        DecisionProviderResponseError: If the response is not an object, or an answer
            for one of ``schema``'s questions is missing or malformed. The message
            names the field.
    """
    body = (
        response.model_dump(mode="json")
        if isinstance(response, BaseModel)
        else response
    )
    if not isinstance(body, dict):
        raise _malformed("<body>", "expected a JSON object for")
    answers = body.get("answers")
    if not isinstance(answers, list):
        raise _malformed("answers")

    questions = schema.questions
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
        structured=DecisionAnswers(schema, parsed),
        reported_model_name=model if isinstance(model, str) else None,
        provider=None,
        input_tokens=_optional_int(usage.get("input_tokens")),
        output_tokens=_optional_int(usage.get("output_tokens")),
        reported_cost=None,
        raw=body,
    )
