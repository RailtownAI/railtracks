# Scope Guard

`ScopeGuard` blocks requests that fall outside what an agent is meant to handle, before the agent's own model is called. A separate judge model labels the latest user message, and the `sensitivity` setting decides which labels are blocked. A blocked request raises `GuardrailBlockedError`, and the guarded agent's model is never called.

## Usage

`scope` is a plain-language description of what the agent covers; it can also list what the agent does not cover, with examples. `model` is the judge model, and a small, cheap model is usually enough. Attach the guard with `model_middleware=[...]`. Put input-transforming guards such as `PIIRedactInputGuard` before it so the judge only sees the transformed text.

```python
--8<-- "docs/scripts/prebuilt_guardrails.py:scope_guard_demo"
```

When a request is blocked, `exc.user_facing_message` holds a fixed English sentence for the label, and `exc.meta["label"]` holds the label so you can show your own text instead.

## Sensitivity

The judge always labels the latest user message with one of three labels, regardless of `sensitivity`.

| Label | Meaning |
|---|---|
| `IN_SCOPE` | The scope covers the request. Greetings, thanks, follow-ups to the current conversation, and questions about what the assistant can do are also `IN_SCOPE`. |
| `UNKNOWN` | The request is unclear even with the earlier conversation, or it is clear but it is not obvious whether the scope covers it. |
| `OUT_OF_SCOPE` | The scope clearly does not cover the request, including requests in the same domain that the scope does not mention. |

`sensitivity` is `"LOW"`, `"MEDIUM"` (the default) or `"HIGH"`, as a string in any case or as `ScopeSensitivity`. It decides which labels are blocked.

| Label | `LOW` | `MEDIUM` | `HIGH` |
|---|---|---|---|
| `IN_SCOPE` | allow | allow | allow |
| `UNKNOWN` | allow | allow | block |
| `OUT_OF_SCOPE` | allow | block | block |

`LOW` never blocks, so it works as an observation mode: run it for a while before launch and look at the labels to see what `MEDIUM` or `HIGH` would block. The labels of allowed requests appear in the output of the `ScopeGuard-judge` node in the visualizer.

!!! note "Scope"
    The judge sees only the text of the latest user message plus up to four earlier user and assistant messages, each cut to its first 500 characters. The latest message is never truncated, so put an `InputLengthGuard` in front of this guard to bound very long inputs. Attachments such as images and PDFs are not judged. The check runs once per agent call: later model calls in the same tool loop are skipped, and so is a history that ends with a tool message. If the judge model fails, the request is allowed. The judge is an extra model call on every request, including with `LOW`. This guard controls cost and keeps the agent on topic; it is not a security boundary against prompt injection.
