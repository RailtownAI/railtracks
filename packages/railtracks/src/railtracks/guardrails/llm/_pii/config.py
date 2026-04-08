from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class PIIEntity(str, Enum):
    """Built-in PII entity types with reliable regex detection."""

    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    PHONE_NUMBER = "PHONE_NUMBER"
    CREDIT_CARD = "CREDIT_CARD"
    US_SSN = "US_SSN"
    CA_SIN = "CA_SIN"
    IP_ADDRESS = "IP_ADDRESS"
    URL = "URL"
    IBAN_CODE = "IBAN_CODE"

    @classmethod
    def available(cls) -> dict[str, str]:
        """Return a mapping of entity name to a human-readable description."""
        return {e.value: _ENTITY_DESCRIPTIONS[e] for e in cls}


_ENTITY_DESCRIPTIONS: dict[PIIEntity, str] = {
    PIIEntity.EMAIL_ADDRESS: "Email addresses (e.g. alice@example.com)",
    PIIEntity.PHONE_NUMBER: "Phone numbers in common formats (e.g. +1 555-867-5309)",
    PIIEntity.CREDIT_CARD: "Credit/debit card numbers validated with Luhn checksum",
    PIIEntity.US_SSN: "US Social Security Numbers (e.g. 123-45-6789)",
    PIIEntity.CA_SIN: "Canadian Social Insurance Numbers (e.g. 046-454-286)",
    PIIEntity.IP_ADDRESS: "IPv4 addresses (e.g. 192.168.1.1)",
    PIIEntity.URL: "URLs starting with http:// or https://",
    PIIEntity.IBAN_CODE: "International Bank Account Numbers (e.g. GB29 NWBK 6016 1331 9268 19)",
}


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
