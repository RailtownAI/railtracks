from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Guard(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    input: list[Any] = Field(default_factory=list)
    output: list[Any] = Field(default_factory=list)
    tool_call: list[Any] = Field(default_factory=list)
    tool_response: list[Any] = Field(default_factory=list)
    fail_open: bool = False
    trace: bool = True

    @field_validator("input", "output", "tool_call", "tool_response")
    @classmethod
    def _validate_callable_rails(cls, value: list[Any]) -> list[Any]:
        for rail in value:
            if not callable(rail):
                raise TypeError(
                    f"Every guardrail must be callable, got {type(rail).__name__}."
                )
        return value
