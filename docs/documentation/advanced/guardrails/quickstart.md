# Guardrails Quickstart

Guardrails are the policy layer around an LLM call in Railtracks. They let you inspect what goes into the model and what comes out, and they can allow, transform, or block the interaction based on your own rules.

In practice, you attach guardrails with `agent_node(..., guardrails=Guard(...))`, then provide one or more rails for the phases you want to control. This quickstart focuses on a small input guard with a real LLM so you can see both outcomes clearly: one request passes through to the model, and one is blocked before inference.

## Minimal setup

```python
--8<-- "docs/scripts/guardrails_quickstart.py:setup"
```

???+ warning "No API key set?"
    Make sure your provider API key is available in your environment or `.env` file.

    ```
    GEMINI_API_KEY="..."
    ```

    Railtracks supports multiple providers. See [Supported Providers](../../../integrations/llms/providers.md).

## Passing request

This request does not match the guardrail, so it reaches the LLM normally.

```python
--8<-- "docs/scripts/guardrails_quickstart.py:pass_case"
```

!!! example "Example output"
    ```text
    LLMResponse(Welcome!)
    ```

## Blocked request

This request contains the blocked keyword, so Railtracks raises `GuardrailBlockedError` instead of calling the model.

```python
--8<-- "docs/scripts/guardrails_quickstart.py:block_case"
```

!!! example "Example output"
    ```text
    Blocked by guardrails (BlockSensitiveRequests): Requests for passwords are not allowed.
    Tips to debug:
    - user_message='Ask for something else instead.'
    ```

