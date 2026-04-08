# Built-in guardrails

This page describes guardrails shipped with Railtracks, how they are organized, and how to try them in isolation with `evaluate()`. For attaching rails to agents and the `Guard` container, see [Overview](overview.md) and [Quickstart](quickstart.md).

## Introduction

**Where they live.** Core types (`Guard`, `InputGuard`, `OutputGuard`, `LLMGuardrailEvent`, `GuardrailDecision`, …) live in the `railtracks.guardrails` package. Built-in LLM guard *implementations* (today: PII redaction) live under `railtracks.guardrails.llm` and are re-exported from that module for a single import path.

```python
--8<-- "docs/scripts/builtin_guardrails_examples.py:core_imports"
```

```python
--8<-- "docs/scripts/builtin_guardrails_examples.py:llm_builtin_imports"
```

**`evaluate()`.** `InputGuard` and `OutputGuard` define `evaluate(...)` so you can run a guard without building an `LLMGuardrailEvent` by hand. For input guards, a `str` is treated as a single user message. For output guards, a `str` becomes the assistant message under inspection. You can also pass `Message`, `MessageHistory`, or a full `LLMGuardrailEvent`. On a match, inspect `GuardrailDecision.messages` (input guard) or `GuardrailDecision.output_message` (output guard) for the rewritten content.

PII guards return `TRANSFORM` when they rewrite text, with redacted content on `decision.messages` (input) or `decision.output_message` (output). They return `ALLOW` when there is nothing to change.

## Contributing a built-in guardrail

1. Implement the guard in `packages/railtracks/src/railtracks/guardrails/llm/` (e.g. `input/` and `output/` modules, shared logic in a private subpackage such as `_pii/`).
2. Subclass `InputGuard` or `OutputGuard`, implement `__call__(self, event: LLMGuardrailEvent) -> GuardrailDecision`, and rely on `evaluate()` from the base class for ad hoc testing.
3. Export public names from `railtracks/guardrails/llm/__init__.py` (and submodules’ `__init__.py` if you split them).
4. Add unit tests under `packages/railtracks/tests/unit_tests/guardrails/`.
5. Extend `docs/scripts/builtin_guardrails_examples.py` with snippet regions and document the guard in this file under **Guardrails**.

Keep dependencies optional or zero unless the feature truly needs them; document behavior, limits, and false-positive/false-negative tradeoffs briefly.

## Guardrails

### PII redaction

`PIIRedactInputGuard` and `PIIRedactOutputGuard` scan **string** message content with regex. Matches are replaced by placeholders such as `[EMAIL_ADDRESS]`. The input guard scans user and system messages; assistant and tool messages are left unchanged. The output guard scans the model’s output message. Non-string content is passed through unchanged.

Detection uses a fixed priority when patterns overlap (for example, email and URL win over the broader phone pattern). `CREDIT_CARD` and `CA_SIN` matches are accepted only when they pass a Luhn checksum check.

#### Entities

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
--8<-- "docs/scripts/builtin_guardrails_examples.py:pii_available"
```

#### Configuration

`PIIRedactConfig` is a **frozen** Pydantic model: default `entities` is the full list above; `custom_patterns` defaults to empty. Each `PIICustomPattern` has a `name` (used in the placeholder) and a `regex` string.

```python
--8<-- "docs/scripts/builtin_guardrails_examples.py:pii_configured_demo"
```

!!! example "Sample `result.messages`"
    ```text
    user: My name is Alice and my email is [EMAIL_ADDRESS] and my SIN is [CA_SIN]
    ```

#### Custom patterns

You are not limited to `PIIEntity` values. Add `PIICustomPattern(name=..., regex=...)` entries to `custom_patterns`; each `name` becomes the placeholder label (for example `EMPLOYEE_ID` produces `[EMPLOYEE_ID]`). Use them alone or together with any built-in entities in the same `PIIRedactConfig`.

```python
--8<-- "docs/scripts/builtin_guardrails_examples.py:pii_custom_patterns"
```

!!! example "Illustrative redacted line"
    For the sample string in the snippet above, the user message content may look like: `My ID is [EMPLOYEE_ID]; contact [EMAIL_ADDRESS] internally.`

Use the same `PIIRedactConfig` instance for both input and output guards if you want identical rules.

#### Agent usage

Attach like any other guard:

```python
--8<-- "docs/scripts/builtin_guardrails_examples.py:agent_guard_attachment"
```

!!! note "Scope"
    This PII layer is regex-only: no NER/Presidio, no `MASK` mode, no streaming-specific API, and no redaction inside tool calls yet. Those may arrive in later releases.
