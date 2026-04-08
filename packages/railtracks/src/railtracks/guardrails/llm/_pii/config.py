from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class PIIEntity(str, Enum):
    """Built-in PII entity types with reliable regex detection."""

    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    PHONE_NUMBER = "PHONE_NUMBER"
    CREDIT_CARD = "CREDIT_CARD"
    US_SSN = "US_SSN"
    IP_ADDRESS = "IP_ADDRESS"
    URL = "URL"
    IBAN_CODE = "IBAN_CODE"


class PIICustomPattern(BaseModel):
    """
    User-defined PII pattern.

    ``name`` becomes the placeholder label: e.g. ``"EMPLOYEE_ID"`` yields
    ``[EMPLOYEE_ID]`` in redacted text.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    regex: str


class PIIRedactConfig(BaseModel):
    """
    Configuration for PII redaction guardrails.

    Frozen so a single instance can safely be shared between input and output
    guard instances.
    """

    model_config = ConfigDict(frozen=True)

    entities: list[PIIEntity] = list(PIIEntity)
    custom_patterns: list[PIICustomPattern] = []
