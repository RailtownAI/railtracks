# Length Limits

`InputLengthGuard` and `OutputLengthGuard` block an LLM interaction when the character count exceeds a configured ceiling. Both return `BLOCK` over the limit and `ALLOW` otherwise; they never transform content.

`InputLengthGuard` sums `len(message.content)` across **all** messages in the input history (user, system, assistant, tool). `OutputLengthGuard` measures the assistant reply on `event.output_message`; if there is no output message, it allows.

## Usage

`max_chars` must be a positive integer; non-positive values raise `ValueError` at construction. Each decision's `meta` carries `total_chars` and `max_chars` for logging.

```python
from railtracks.prebuilt.guardrails import InputLengthGuard, OutputLengthGuard


input_length = InputLengthGuard(max_chars=4000)

result = input_length.decide("a" * 5000)
# result.action == rt.guardrails.GuardrailAction.BLOCK
# result.meta == {"total_chars": 5000, "max_chars": 4000}
```

```python
output_length = OutputLengthGuard(max_chars=2000)

result = output_length.decide("ok")
# result.action == rt.guardrails.GuardrailAction.ALLOW
```

Scope

Counting is character-based and dependency-free. Word- or token-based counting (e.g. via `tiktoken`) is out of scope today and may arrive in later releases. Non-string content is treated as zero-length.
