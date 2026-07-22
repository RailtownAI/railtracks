# PII Redaction

`PIIRedactInputGuard` and `PIIRedactOutputGuard` scan **string** message content with regex and replace matches with placeholders such as `[EMAIL_ADDRESS]`. The input guard scans user and system messages; assistant and tool messages are left unchanged. The output guard scans the model's output message. Non-string content is passed through unchanged.

Detection uses a fixed priority when patterns overlap (for example, email and URL win over the broader phone pattern). `CREDIT_CARD` and `CA_SIN` matches are accepted only when they pass a Luhn checksum check. These guards return `TRANSFORM` when they rewrite text and `ALLOW` when there is nothing to change.


## Entities

Built-in entity enum `PIIEntity` includes:

| Entity | Notes |
|--------|--------|
| `EMAIL_ADDRESS` | Common email shapes |
| `PHONE_NUMBER` | `+country`, parentheses, dots, dashes; 7–10 digit core |
| `CREDIT_CARD` | 13–16 digit groups, Luhn-validated |
| `US_SSN` | `###-##-####` with word boundaries |
| `CA_SIN` | Canadian SIN `###-###-###`, Luhn-validated |
| `IP_ADDRESS` | IPv4 |
| `URL` | `http://` or `https://` only |
| `IBAN_CODE` | IBAN with optional spaces |

Discover names and short descriptions at runtime:

```python
--8<-- "docs/scripts/prebuilt_guardrails.py:pii_available"
```

## Configuration

`PIIRedactConfig` is a **frozen** Pydantic model: default `entities` is the full list above; `custom_patterns` defaults to empty.

```python
--8<-- "docs/scripts/prebuilt_guardrails.py:pii_configured_demo"
```

!!! example "Sample `result.messages`"
    ```text
    user: My name is Alice and my email is [EMAIL_ADDRESS] and my SIN is [CA_SIN]
    ```

## Custom patterns

You are not limited to `PIIEntity` values. Add `PIICustomPattern(name=..., regex=...)` entries to `custom_patterns`; each `name` becomes the placeholder label (for example `EMPLOYEE_ID` produces `[EMPLOYEE_ID]`). Use them alone or together with any built-in entities in the same `PIIRedactConfig`.

```python
--8<-- "docs/scripts/prebuilt_guardrails.py:pii_custom_patterns"
```

Use the same `PIIRedactConfig` instance for both input and output guards if you want identical rules.

## Agent usage

Attach them as model middleware:

```python
--8<-- "docs/scripts/prebuilt_guardrails.py:pii_agent"
```

!!! note "Scope"
    This PII layer is regex-only: no NER/Presidio, no `MASK` mode, no streaming-specific API, and no redaction inside tool calls yet. Those may arrive in later releases.
