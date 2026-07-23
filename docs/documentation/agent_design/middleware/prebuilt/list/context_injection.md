# Context Injection

`ContextInjection` fills `{placeholder}` templates in your prompt from the active session context before each model call. Write `{user_name}` in a system or user message, put `user_name` in the flow context, and the model sees the resolved value. It is **model-level only** (`model_middleware=`).


## Usage

```python
--8<-- "docs/scripts/prebuilt_middleware.py:context_injection"
```

!!! note "Ordering"
    List position matters: place `ContextInjection` before (outside) any middleware that must see the injected prompt. For example, an input guard listed after it will see the filled-in template rather than the raw `{placeholder}`.
