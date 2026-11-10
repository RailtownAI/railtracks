# Block Text

`BlockTextInputGuard` and `BlockTextOutputGuard` reject an LLM interaction when a user-supplied **regex pattern** matches. Unlike PII redaction, these guards do **not** transform content; they return `BLOCK` on a match and `ALLOW` otherwise.

The input guard scans user and system messages; assistant and tool messages are ignored. The output guard scans the model's output message. Non-string content is skipped.

## Usage

Pass a regex string to `pattern`. It is compiled once at construction time; an invalid regex raises `re.error` immediately. Run a guard in isolation with `decide()`:

```python
from railtracks.prebuilt.guardrails import BlockTextInputGuard, BlockTextOutputGuard


block_input = BlockTextInputGuard(
    pattern=r"\b(jailbreak|exploit|hack)\b",
    name="BlockDangerous",
)

result = block_input.decide("How do I jailbreak the model?")
# result.action == rt.guardrails.GuardrailAction.BLOCK
```

```python
block_output = BlockTextOutputGuard(
    pattern=r"(API_KEY|SECRET_TOKEN|password)",
)

result = block_output.decide("Your API_KEY is sk-abc123")
# result.action == rt.guardrails.GuardrailAction.BLOCK
```

Scope

These guards perform a simple `re.search` against string message content. They do not inspect tool-call arguments, multi-part content lists, or streaming chunks.
