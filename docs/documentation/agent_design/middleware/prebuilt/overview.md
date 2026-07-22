# Prebuilt Middleware

Railtracks ships a suite of prebuilt middleware so you can add common behavior to an agent without writing it yourself. Every item below is a normal middleware; you attach it exactly like your own, on the `middleware=` (node) or `model_middleware=` (model) slot. For the difference between the two slots, see [Middleware Overview](../overview.md); to build your own, see [Custom Middleware](../custom.md).

The **Slot** column tells you where each middleware can be attached:

- **Node**: wraps the whole node/function call (`middleware=`).
- **Model**: wraps a single model call (`model_middleware=`).
- **Both**: slot-agnostic; works in either.

## Catalog

| Middleware | Slot | What it does |
|---|---|---|
| [Retry](list/retry.md) | Both | Re-run the wrapped call when it raises a transient error, with a configurable backoff. |
| [ContextInjection](list/context_injection.md) | Model | Fill `{placeholder}` templates in the prompt from the active session context. |

### Guardrails

Guardrails are model middleware too; a policy layer that inspects inputs and outputs and can allow, transform, or block them. See the [Guardrails](../guardrails/overview.md) overview for the full picture; the prebuilt rails are catalogued here.

| Guardrail | Slot | What it does |
|---|---|---|
| [BlockTextInputGuard / BlockTextOutputGuard](list/block_text.md) | Model | Block an interaction when a regex pattern matches the input or output. |
| [InputLengthGuard / OutputLengthGuard](list/length.md) | Model | Block an interaction when the character count exceeds a ceiling. |
| [PIIRedactInputGuard / PIIRedactOutputGuard](list/pii_redaction.md) | Model | Redact PII (emails, phone numbers, custom patterns, …) from inputs and outputs. |

!!! Note
    Don't see what you are looking for? [Create your own middleware](../custom.md) for a custom solution, or [contribute a prebuilt middleware](contributions.md) so others can reuse it.
