"""Runnable examples for the prebuilt guardrails docs.

Snippet regions (--8<-- [start:name]) are pulled into the prebuilt guardrail
pages by MkDocs. Type-checked in CI via scripts/docs_validation.sh.

Prebuilt guards are model middleware: attach them with
``agent_node(..., model_middleware=[...])``.
"""

from __future__ import annotations

import railtracks as rt

# --8<-- [start: imports]
from railtracks.prebuilt.guardrails import (
    BlockTextInputGuard,
    BlockTextOutputGuard,
    InputLengthGuard,
    OutputLengthGuard,
    PIICustomPattern,
    PIIEntity,
    PIIRedactConfig,
    PIIRedactInputGuard,
    PIIRedactOutputGuard,
)

# --8<-- [end: imports]


# --8<-- [start: block_text_demo]
from railtracks.prebuilt.guardrails import BlockTextInputGuard, BlockTextOutputGuard


block_input = BlockTextInputGuard(
    pattern=r"\b(jailbreak|exploit|hack)\b",
    name="BlockDangerous",
)

result = block_input.decide("How do I jailbreak the model?")
# result.action == rt.guardrails.GuardrailAction.BLOCK
# --8<-- [end: block_text_demo]

# --8<-- [start: block_text_output_demo]
block_output = BlockTextOutputGuard(
    pattern=r"(API_KEY|SECRET_TOKEN|password)",
)

result = block_output.decide("Your API_KEY is sk-abc123")
# result.action == rt.guardrails.GuardrailAction.BLOCK
# --8<-- [end: block_text_output_demo]


# --8<-- [start: length_input_demo]
from railtracks.prebuilt.guardrails import InputLengthGuard, OutputLengthGuard


input_length = InputLengthGuard(max_chars=4000)

result = input_length.decide("a" * 5000)
# result.action == rt.guardrails.GuardrailAction.BLOCK
# result.meta == {"total_chars": 5000, "max_chars": 4000}
# --8<-- [end: length_input_demo]

# --8<-- [start: length_output_demo]
output_length = OutputLengthGuard(max_chars=2000)

result = output_length.decide("ok")
# result.action == rt.guardrails.GuardrailAction.ALLOW
# --8<-- [end: length_output_demo]


# --8<-- [start: pii_available]
from railtracks.prebuilt.guardrails import PIIEntity


names_to_help = PIIEntity.available()
# e.g. {"EMAIL_ADDRESS": "Email addresses (e.g. alice@example.com)", ...}
# --8<-- [end: pii_available]

# --8<-- [start: pii_configured_demo]
from railtracks.prebuilt.guardrails import (
    PIIEntity,
    PIIRedactConfig,
    PIIRedactInputGuard
)


config = PIIRedactConfig(
    entities=[
        PIIEntity.EMAIL_ADDRESS,
        PIIEntity.CA_SIN,
    ]
)

redact_input = PIIRedactInputGuard(config=config, name="RedactEmail")

msg = "My name is Alice and my email is alice@example.com and my SIN is 163-180-003"
result = redact_input.decide(msg)
# result.messages — redacted user message(s)
# --8<-- [end: pii_configured_demo]

# --8<-- [start: pii_custom_patterns]
from railtracks.prebuilt.guardrails import (
    PIIEntity,
    PIIRedactConfig,
    PIIRedactInputGuard,
    PIICustomPattern
)


custom_config = PIIRedactConfig(
    entities=[PIIEntity.EMAIL_ADDRESS],
    custom_patterns=[
        PIICustomPattern(name="EMPLOYEE_ID", regex=r"\bEMP-\d{6}\b"),
    ],
)

guard_with_custom = PIIRedactInputGuard(config=custom_config)

result = guard_with_custom.decide(
    "My ID is EMP-123456; contact hr@company.example internally."
)
# result.messages — redacted user message(s), e.g. [EMPLOYEE_ID] and [EMAIL_ADDRESS]
# --8<-- [end: pii_custom_patterns]


def main() -> None:
    print("PIIEntity.available() keys:", sorted(PIIEntity.available().keys()))
    cfg = PIIRedactConfig(entities=[PIIEntity.EMAIL_ADDRESS, PIIEntity.CA_SIN])
    demo_guard = PIIRedactInputGuard(config=cfg, name="RedactEmail")
    demo_msg = (
        "My name is Alice and my email is alice@example.com and my SIN is 163-180-003"
    )
    print(demo_guard.decide(demo_msg).messages)


if __name__ == "__main__":
    main()
