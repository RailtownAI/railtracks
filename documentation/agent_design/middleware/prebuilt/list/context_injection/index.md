# ContextInjection

`ContextInjection` fills `{placeholder}` templates in your prompt from the active session context before each model call. Write `{user_name}` in a system or user message, put `user_name` in the flow context, and the model sees the resolved value. It is **model-level only** (`model_middleware=`).

## Usage

```python
import railtracks as rt
from railtracks.prebuilt.middleware import ContextInjection

# ContextInjection is model-level only. It fills {placeholders} in the prompt
# from the active session context before each model call.
CtxAgent = rt.agent_node(
    name="context-injection-demo",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are helping {user_name}. Keep answers short.",
    model_middleware=[ContextInjection()],
)

flow = rt.Flow(
    "ContextInjectionFlow",
    entry_point=CtxAgent,
    context={"user_name": "Alex"},
)
# flow.invoke("Who are you helping?")  ->  the model sees "You are helping Alex."
```

Ordering

List position matters: place `ContextInjection` before (outside) any middleware that must see the injected prompt. For example, an input guard listed after it will see the filled-in template rather than the raw `{placeholder}`.
