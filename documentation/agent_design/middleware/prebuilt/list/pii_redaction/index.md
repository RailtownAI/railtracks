# PII Redaction

`PIIRedactInputGuard` and `PIIRedactOutputGuard` scan **string** message content with regex and replace matches with placeholders such as `[EMAIL_ADDRESS]`. The input guard scans user and system messages; assistant and tool messages are left unchanged. The output guard scans the model's output message. Non-string content is passed through unchanged.

Detection uses a fixed priority when patterns overlap (for example, email and URL win over the broader phone pattern). `CREDIT_CARD` and `CA_SIN` matches are accepted only when they pass a Luhn checksum check. These guards return `TRANSFORM` when they rewrite text and `ALLOW` when there is nothing to change.

## Entities

Built-in entity enum `PIIEntity` includes:

| Entity          | Notes                                                  |
| --------------- | ------------------------------------------------------ |
| `EMAIL_ADDRESS` | Common email shapes                                    |
| `PHONE_NUMBER`  | `+country`, parentheses, dots, dashes; 7–10 digit core |
| `CREDIT_CARD`   | 13–16 digit groups, Luhn-validated                     |
| `US_SSN`        | `###-##-####` with word boundaries                     |
| `CA_SIN`        | Canadian SIN `###-###-###`, Luhn-validated             |
| `IP_ADDRESS`    | IPv4                                                   |
| `URL`           | `http://` or `https://` only                           |
| `IBAN_CODE`     | IBAN with optional spaces                              |

Discover names and short descriptions at runtime:

```python
from railtracks.prebuilt.guardrails import PIIEntity


names_to_help = PIIEntity.available()
# e.g. {"EMAIL_ADDRESS": "Email addresses (e.g. alice@example.com)", ...}
```

## Configuration

`PIIRedactConfig` is a **frozen** Pydantic model: default `entities` is the full list above; `custom_patterns` defaults to empty.

```python
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
# result.messages: redacted user message(s)
```

Sample `result.messages`

```text
user: My name is Alice and my email is [EMAIL_ADDRESS] and my SIN is [CA_SIN]
```

## Custom patterns

You are not limited to `PIIEntity` values. Add `PIICustomPattern(name=..., regex=...)` entries to `custom_patterns`; each `name` becomes the placeholder label (for example `EMPLOYEE_ID` produces `[EMPLOYEE_ID]`). Use them alone or together with any built-in entities in the same `PIIRedactConfig`.

```python
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
# result.messages: redacted user message(s), e.g. [EMPLOYEE_ID] and [EMAIL_ADDRESS]
```

Use the same `PIIRedactConfig` instance for both input and output guards if you want identical rules.
