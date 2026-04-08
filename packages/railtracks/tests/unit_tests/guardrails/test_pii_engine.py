"""Tests for the PII detection and redaction engine."""

from __future__ import annotations

import pytest

from railtracks.guardrails.llm._pii.config import (
    PIICustomPattern,
    PIIEntity,
    PIIRedactConfig,
)
from railtracks.guardrails.llm._pii.engine import PIIEngine, RedactionRecord


@pytest.fixture
def all_entities_engine() -> PIIEngine:
    return PIIEngine(PIIRedactConfig())


class TestEmailRedaction:
    def test_email_redacted(self, all_entities_engine: PIIEngine) -> None:
        text = "Contact alice@example.com for details."
        result, records = all_entities_engine.redact(text)
        assert result == "Contact [EMAIL_ADDRESS] for details."
        assert len(records) == 1
        assert records[0].entity_type == "EMAIL_ADDRESS"

    def test_multiple_emails(self, all_entities_engine: PIIEngine) -> None:
        text = "From alice@example.com to bob@test.org"
        result, records = all_entities_engine.redact(text)
        assert "[EMAIL_ADDRESS]" in result
        assert result.count("[EMAIL_ADDRESS]") == 2
        assert len(records) == 2


class TestPhoneRedaction:
    def test_us_phone_with_country_code(self, all_entities_engine: PIIEngine) -> None:
        text = "Call +1 555-867-5309 now."
        result, records = all_entities_engine.redact(text)
        assert "[PHONE_NUMBER]" in result
        assert len(records) == 1

    def test_phone_with_parens(self, all_entities_engine: PIIEngine) -> None:
        text = "Call (555) 867-5309 now."
        result, records = all_entities_engine.redact(text)
        assert "[PHONE_NUMBER]" in result

    def test_phone_with_dots(self, all_entities_engine: PIIEngine) -> None:
        text = "Call 555.867.5309 now."
        result, records = all_entities_engine.redact(text)
        assert "[PHONE_NUMBER]" in result


class TestCreditCardRedaction:
    def test_valid_luhn(self, all_entities_engine: PIIEngine) -> None:
        text = "Card: 4111 1111 1111 1111 on file."
        result, records = all_entities_engine.redact(text)
        assert "[CREDIT_CARD]" in result
        assert len(records) == 1

    def test_invalid_luhn_not_redacted(self, all_entities_engine: PIIEngine) -> None:
        config = PIIRedactConfig(entities=[PIIEntity.CREDIT_CARD])
        engine = PIIEngine(config)
        text = "Number: 1234 5678 9012 3456 here."
        result, records = engine.redact(text)
        assert "1234 5678 9012 3456" in result
        assert not any(r.entity_type == "CREDIT_CARD" for r in records)

    def test_visa_no_spaces(self, all_entities_engine: PIIEngine) -> None:
        text = "Card: 4111111111111111 on file."
        result, records = all_entities_engine.redact(text)
        assert "[CREDIT_CARD]" in result


class TestSSNRedaction:
    def test_ssn_redacted(self, all_entities_engine: PIIEngine) -> None:
        text = "SSN is 123-45-6789 here."
        result, records = all_entities_engine.redact(text)
        assert result == "SSN is [US_SSN] here."
        assert len(records) == 1
        assert records[0].entity_type == "US_SSN"


class TestCASINRedaction:
    def test_valid_sin_redacted(self, all_entities_engine: PIIEngine) -> None:
        text = "My SIN is 046-454-286 on file."
        result, records = all_entities_engine.redact(text)
        assert result == "My SIN is [CA_SIN] on file."
        assert len(records) == 1
        assert records[0].entity_type == "CA_SIN"

    def test_invalid_luhn_sin_not_redacted(self) -> None:
        config = PIIRedactConfig(entities=[PIIEntity.CA_SIN])
        engine = PIIEngine(config)
        text = "Number 111-222-333 here."
        result, records = engine.redact(text)
        assert "111-222-333" in result
        assert not any(r.entity_type == "CA_SIN" for r in records)


class TestIPAddressRedaction:
    def test_ipv4_redacted(self, all_entities_engine: PIIEngine) -> None:
        text = "Server at 192.168.1.1 is down."
        result, records = all_entities_engine.redact(text)
        assert result == "Server at [IP_ADDRESS] is down."
        assert len(records) == 1


class TestURLRedaction:
    def test_https_url_redacted(self, all_entities_engine: PIIEngine) -> None:
        text = "Visit https://internal.corp/api/v2 for docs."
        result, records = all_entities_engine.redact(text)
        assert "[URL]" in result
        assert len(records) == 1

    def test_http_url_redacted(self, all_entities_engine: PIIEngine) -> None:
        text = "See http://example.com/page?q=1"
        result, records = all_entities_engine.redact(text)
        assert "[URL]" in result


class TestIBANRedaction:
    def test_iban_redacted(self, all_entities_engine: PIIEngine) -> None:
        text = "Transfer to GB29 NWBK 6016 1331 9268 19 please."
        result, records = all_entities_engine.redact(text)
        assert "[IBAN_CODE]" in result
        assert len(records) == 1

    def test_iban_no_spaces(self, all_entities_engine: PIIEngine) -> None:
        text = "IBAN: GB29NWBK60161331926819 here."
        result, records = all_entities_engine.redact(text)
        assert "[IBAN_CODE]" in result


class TestCustomPattern:
    def test_custom_pattern_fires(self) -> None:
        config = PIIRedactConfig(
            entities=[],
            custom_patterns=[
                PIICustomPattern(name="EMPLOYEE_ID", regex=r"\bEMP-\d{6}\b"),
            ],
        )
        engine = PIIEngine(config)
        text = "Employee EMP-123456 reported the issue."
        result, records = engine.redact(text)
        assert result == "Employee [EMPLOYEE_ID] reported the issue."
        assert len(records) == 1
        assert records[0].entity_type == "EMPLOYEE_ID"
        assert records[0].placeholder == "[EMPLOYEE_ID]"


class TestSpanMerging:
    def test_overlap_keeps_longer_span(self) -> None:
        config = PIIRedactConfig(
            entities=[PIIEntity.US_SSN],
            custom_patterns=[
                PIICustomPattern(name="WIDE_DIGITS", regex=r"\d{3}-\d{2}-\d{4}\b"),
            ],
        )
        engine = PIIEngine(config)
        text = "Value: 123-45-6789 done."
        result, records = engine.redact(text)
        assert result.count("[") == 1
        assert len(records) == 1


class TestCleanText:
    def test_no_pii_returns_original(self, all_entities_engine: PIIEngine) -> None:
        text = "Hello, this is a perfectly clean message."
        result, records = all_entities_engine.redact(text)
        assert result == text
        assert records == []


class TestMultipleEntities:
    def test_email_and_phone_in_same_text(
        self, all_entities_engine: PIIEngine
    ) -> None:
        text = "Email alice@example.com or call +1 555-867-5309."
        result, records = all_entities_engine.redact(text)
        assert "[EMAIL_ADDRESS]" in result
        assert "[PHONE_NUMBER]" in result
        assert len(records) == 2


class TestRecordFields:
    def test_record_has_correct_fields(self, all_entities_engine: PIIEngine) -> None:
        text = "SSN is 123-45-6789 here."
        _, records = all_entities_engine.redact(text)
        assert len(records) == 1
        r = records[0]
        assert r.entity_type == "US_SSN"
        assert r.placeholder == "[US_SSN]"
        assert r.start == 7
        assert r.end == 18
        assert isinstance(r, RedactionRecord)

    def test_record_does_not_store_raw_value(
        self, all_entities_engine: PIIEngine
    ) -> None:
        text = "SSN is 123-45-6789 here."
        _, records = all_entities_engine.redact(text)
        r = records[0]
        dumped = r.model_dump()
        for v in dumped.values():
            if isinstance(v, str):
                assert "123-45-6789" not in v
