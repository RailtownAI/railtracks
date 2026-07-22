# Length Limits

`InputLengthGuard` and `OutputLengthGuard` block an LLM interaction when the character count exceeds a configured ceiling. Both return `BLOCK` over the limit and `ALLOW` otherwise; they never transform content.

`InputLengthGuard` sums `len(message.content)` across **all** messages in the input history (user, system, assistant, tool). `OutputLengthGuard` measures the assistant reply on `event.output_message`; if there is no output message, it allows.


## Usage

`max_chars` must be a positive integer; non-positive values raise `ValueError` at construction. Each decision's `meta` carries `total_chars` and `max_chars` for logging.

```python
--8<-- "docs/scripts/prebuilt_guardrails.py:length_input_demo"
```

```python
--8<-- "docs/scripts/prebuilt_guardrails.py:length_output_demo"
```

Attach them as model middleware:

```python
--8<-- "docs/scripts/prebuilt_guardrails.py:length_agent"
```

!!! note "Scope"
    Counting is character-based and dependency-free. Word- or token-based counting (e.g. via `tiktoken`) is out of scope today and may arrive in later releases. Non-string content is treated as zero-length.
