# Scope Guard

`ScopeGuard` blocks requests that fall outside what an agent is meant to handle, before the agent's own model is called. A separate judge model labels the latest user message, and the `sensitivity` setting decides which labels are blocked. A blocked request raises `GuardrailBlockedError`, and the guarded agent's model is never called.

## Usage

`scope` is a plain-language description of what the agent covers; it can also list what the agent does not cover, with examples. `model` is the judge model. It must support structured output, because the judge answers with a fixed JSON shape; a model that does not will fail every check and, with the default `fail_open=True`, quietly turn the guard off, so check the `error` traces after switching models. A small, fast model such as `gpt-6-luna` is enough. Attach the guard with `model_middleware=[...]`. Put input-transforming guards such as `PIIRedactInputGuard` before it so the judge only sees the transformed text.

```python
from railtracks.guardrails import GuardrailBlockedError

scope_guard = ScopeGuard(
    scope=(
        "You are the customer-support assistant for a cupcake bakery: orders, flavours, allergens and delivery. "
        "You do not give general baking recipes or help with anything unrelated to the bakery."
    ),
    model=rt.llm.OpenAILLM("gpt-6-luna"),
    sensitivity=ScopeSensitivity.HIGH,
)

BakeryAgent = rt.agent_node(
    name="bakery",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You answer customer questions for a cupcake bakery.",
    # PII is redacted first, so the judge only sees the redacted text
    model_middleware=[PIIRedactInputGuard(), scope_guard],
)

flow = rt.Flow("bakery", entry_point=BakeryAgent)

# answer("Do you have gluten-free cupcakes?") reaches the bakery agent;
# answer("Write me a Python script") is blocked before it is called.


def answer(user_text: str) -> str:
    try:
        return flow.invoke(user_text).text
    except GuardrailBlockedError as exc:
        return exc.user_facing_message or "Request blocked."
```

When a request is blocked, `exc.user_facing_message` holds a fixed English sentence for the label, and `exc.meta["label"]` holds the label so you can show your own text instead.

## Sensitivity

The judge always labels the latest user message with one of three labels, regardless of `sensitivity`.

| Label          | Meaning                                                                                                                                                     |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `IN_SCOPE`     | The scope covers the request. Greetings, thanks, follow-ups to the current conversation, and questions about what the assistant can do are also `IN_SCOPE`. |
| `UNKNOWN`      | The request is unclear even with the earlier conversation, or it is clear but it is not obvious whether the scope covers it.                                |
| `OUT_OF_SCOPE` | The scope clearly does not cover the request, including requests in the same domain that the scope does not mention.                                        |

`sensitivity` is `"LOW"`, `"MEDIUM"` (the default) or `"HIGH"`, as a string in any case or as `ScopeSensitivity`. It decides which labels are blocked.

| Label          | `LOW` | `MEDIUM` | `HIGH` |
| -------------- | ----- | -------- | ------ |
| `IN_SCOPE`     | allow | allow    | allow  |
| `UNKNOWN`      | allow | allow    | block  |
| `OUT_OF_SCOPE` | allow | block    | block  |

`LOW` never blocks, so it works as an observation mode: run it for a while before launch and look at the labels to see what `MEDIUM` or `HIGH` would block. The labels of allowed requests appear in the output of the `ScopeGuard-judge` node in the visualizer.

Scope

The judge sees only the text of the latest user message plus up to four earlier user and assistant messages, each cut to its first 500 characters. The latest message is never truncated, so put an `InputLengthGuard` in front of this guard to bound very long inputs. Attachments such as images and PDFs are not judged. The check runs once per agent call: later model calls in the same tool loop are skipped, and so is a history that ends with a tool message. The judge does run again if the agent re-calls its model for another reason, such as a structured-output retry. If the judge model fails, the request is allowed by default, unlike the other prebuilt guards; pass `fail_open=False` to block the request instead. The judge is an extra model call on every request, including with `LOW`. This guard controls cost and keeps the agent on topic; it is not a security boundary against prompt injection.
