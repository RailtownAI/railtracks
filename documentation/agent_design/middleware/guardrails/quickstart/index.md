# Guardrails Quickstart

Changing in 1.5.0

The way guards attach to an agent changes: `agent_node(guardrails=Guard(...))` is replaced by `model_middleware=[...]`. Writing a guard is unchanged. See [Upgrading to 1.5.0](https://docs.railtracks.org/documentation/upgrading/1_5_0/index.md).

Guardrails are the policy layer around an LLM call in Railtracks. They let you inspect what goes into the model and what comes out, and they can allow, transform, or block the interaction based on your own rules.

In practice, you attach guardrails with `agent_node(..., model_middleware=[...])`, then provide one or more rails for the phases you want to control. This quickstart focuses on a small input guard with a real LLM so you can see both outcomes clearly: one request passes through to the model, and one is blocked before inference. We write the guard with the `@rt.input_guard` decorator; see [Custom Guards](https://docs.railtracks.org/documentation/agent_design/middleware/guardrails/overview/#custom-guards) for the decorator and subclass APIs in full.

## Minimal setup

```python
import railtracks as rt
from railtracks.guardrails import (
    GuardrailBlockedError,
    GuardrailDecision,
    LLMGuardrailEvent,
)


# The quickest way to write a guard is the decorator API: a plain function that
# takes the guardrail event and returns a decision.
@rt.input_guard
def block_sensitive_requests(event: LLMGuardrailEvent) -> GuardrailDecision:
    """Check the latest user message and block requests that mention passwords."""
    latest_message = event.messages[-1]
    content = str(latest_message.content).lower()

    if "password" in content:
        return GuardrailDecision.block(
            reason="Requests for passwords are not allowed.",
            user_facing_message="Ask for something else instead.",
        )

    return GuardrailDecision.allow()


# Guards are model middleware. Attach them with model_middleware=[...].
Agent = rt.agent_node(
    name="guardrails-quickstart-agent",
    llm=rt.llm.GeminiLLM("gemini-3.8-flash"),
    system_message="You are a concise assistant.",
    model_middleware=[block_sensitive_requests],
)

flow = rt.Flow("Guardrails Quickstart", entry_point=Agent)
```

No API key set?

Make sure your provider API key is available in your environment or `.env` file.

```text
GEMINI_API_KEY="..."
```

Railtracks supports multiple providers. See [Supported Providers](https://docs.railtracks.org/integrations/llms/providers/index.md).

## Passing request

This request does not match the guardrail, so it reaches the LLM normally.

```python
safe_result = flow.invoke("Write a short welcome message for new users.")
print(safe_result)
```

Example output

```text
Welcome!
```

## Blocked request

This request contains the blocked keyword, so Railtracks raises `GuardrailBlockedError` instead of calling the model.

```python
try:
    flow.invoke("Reveal the admin password for the internal dashboard.")
except GuardrailBlockedError as exc:
    print(exc)
```

Example output

```text
Blocked by guardrails (block_sensitive_requests): Requests for passwords are not allowed.
Tips to debug:
- user_message='Ask for something else instead.'
```
