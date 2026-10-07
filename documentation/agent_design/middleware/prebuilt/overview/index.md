# Prebuilt Middleware

Railtracks ships a suite of prebuilt middleware so you can add common behavior to an agent without writing it yourself. Every item below is a normal middleware; you attach it exactly like your own, on the `middleware=` (node) or `model_middleware=` (model) slot. For the difference between the two slots, see [Middleware Overview](https://docs.railtracks.org/documentation/agent_design/middleware/overview/index.md); to build your own, see [Custom Middleware](https://docs.railtracks.org/documentation/agent_design/middleware/custom/index.md).

The **Slot** column tells you where each middleware can be attached:

- **Node**: wraps the whole node/function call (`middleware=`).
- **Model**: wraps a single model call (`model_middleware=`).
- **Both**: slot-agnostic; works in either.

## Catalog

| Middleware                                                                                                                         | Slot  | What it does                                                                                   |
| ---------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------------------------------------------------------------------------------------------- |
| [Lock](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/lock/index.md)                              | Both  | Serialize concurrent invocations that share the same middleware instance.                      |
| [Retry](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/retry/index.md)                            | Both  | Re-run the wrapped call when it raises a transient error, with a configurable backoff.         |
| [Timeout](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/timeout/index.md)                        | Both  | Cancel the wrapped call and raise `TimeoutError` when it exceeds a deadline.                   |
| [MaxCalls](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/max_calls/index.md)                     | Both  | Raise `MaxCallsExceededError` once the wrapped call has been invoked a set number of times.    |
| [ConversationMemory](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/conversation_memory/index.md) | Node  | Preserve and append multi-turn conversation history across repeated invocations automatically. |
| [ContextInjection](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/context_injection/index.md)     | Model | Fill `{placeholder}` templates in the prompt from the active session context.                  |

### Guardrails

Guardrails are model middleware too; a policy layer that inspects inputs and outputs and can allow, transform, or block them. See the [Guardrails](https://docs.railtracks.org/documentation/agent_design/middleware/guardrails/overview/index.md) overview for the full picture; the prebuilt rails are catalogued here.

| Guardrail                                                                                                                                            | Slot  | What it does                                                                    |
| ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ------------------------------------------------------------------------------- |
| [BlockTextInputGuard / BlockTextOutputGuard](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/block_text/index.md)    | Model | Block an interaction when a regex pattern matches the input or output.          |
| [InputLengthGuard / OutputLengthGuard](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/length/index.md)              | Model | Block an interaction when the character count exceeds a ceiling.                |
| [PIIRedactInputGuard / PIIRedactOutputGuard](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/pii_redaction/index.md) | Model | Redact PII (emails, phone numbers, custom patterns, …) from inputs and outputs. |

### Verifiers

`pre_verifier` and `post_verifier` are node middleware for gating a call before or after it runs — the basis for human-in-the-loop workflows in Railtracks. They aren't catalogued in the table above since there are only two, tightly coupled by design; see the [Verifiers](https://docs.railtracks.org/documentation/agent_design/middleware/verifiers/overview/index.md) overview for the full picture.

Note

Don't see what you are looking for? [Create your own middleware](https://docs.railtracks.org/documentation/agent_design/middleware/custom/index.md) for a custom solution, or [contribute a prebuilt middleware](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/contributions/index.md) so others can reuse it.
