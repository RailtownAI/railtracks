"""
Examples for docs/guardrails/builtin_guardrails.md.

Snippet markers (--8<-- [start:name]) are consumed by MkDocs snippets;
run from repo root: uv run python docs/scripts/builtin_guardrails_examples.py
"""

from __future__ import annotations

# --8<-- [start:core_imports]
from railtracks.guardrails import (
    Guard,
    GuardrailDecision,
    InputGuard,
    LLMGuardrailEvent,
    OutputGuard,
)
# --8<-- [end:core_imports]

# --8<-- [start:llm_builtin_imports]
from railtracks.guardrails.llm import (
    PIICustomPattern,
    PIIEntity,
    PIIRedactConfig,
    PIIRedactInputGuard,
    PIIRedactOutputGuard,
)
# --8<-- [end:llm_builtin_imports]

# --8<-- [start:pii_available]
names_to_help = PIIEntity.available()
# e.g. {"EMAIL_ADDRESS": "Email addresses (e.g. alice@example.com)", ...}
# --8<-- [end:pii_available]

# --8<-- [start:pii_configured_demo]
config = PIIRedactConfig(
    entities=[
        PIIEntity.EMAIL_ADDRESS,
        PIIEntity.CA_SIN,
    ]
)

redact_input = PIIRedactInputGuard(config=config, name="RedactEmail")

msg = (
    "My name is Alice and my email is alice@example.com "
    "and my SIN is 163-180-003"
)
result = redact_input.evaluate(msg)
# result.messages — redacted user message(s)
# --8<-- [end:pii_configured_demo]

# --8<-- [start:pii_custom_patterns]
custom_config = PIIRedactConfig(
    entities=[PIIEntity.EMAIL_ADDRESS],
    custom_patterns=[
        PIICustomPattern(name="EMPLOYEE_ID", regex=r"\bEMP-\d{6}\b"),
    ],
)

guard_with_custom = PIIRedactInputGuard(config=custom_config)

result = guard_with_custom.evaluate(
    "My ID is EMP-123456; contact hr@company.example internally."
)
# result.messages — redacted user message(s), e.g. [EMPLOYEE_ID] and [EMAIL_ADDRESS]
# --8<-- [end:pii_custom_patterns]

# --8<-- [start:agent_guard_attachment]
import railtracks as rt

Agent = rt.agent_node(
    name="pii-redact-demo",
    llm=rt.llm.GeminiLLM("gemini-2.5-flash"),
    system_message="You are a concise assistant.",
    guardrails=Guard(
        input=[PIIRedactInputGuard()],
        output=[PIIRedactOutputGuard()],
    ),
)
# --8<-- [end:agent_guard_attachment]


def main() -> None:
    print("PIIEntity.available() keys:", sorted(PIIEntity.available().keys()))
    cfg = PIIRedactConfig(entities=[PIIEntity.EMAIL_ADDRESS, PIIEntity.CA_SIN])
    demo_guard = PIIRedactInputGuard(config=cfg, name="RedactEmail")
    demo_msg = (
        "My name is Alice and my email is alice@example.com "
        "and my SIN is 163-180-003"
    )
    print(demo_guard.evaluate(demo_msg).messages)


if __name__ == "__main__":
    main()
