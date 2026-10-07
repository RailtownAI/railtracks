# Timeout

`Timeout` limits how long a wrapped call may run. If the deadline expires, it cancels the call and raises `TimeoutError` instead of allowing a slow node or model request to halt the workflow indefinitely.

```python
import railtracks as rt
from railtracks.prebuilt.middleware import Timeout

TimedAgent = rt.agent_node(
    name="timeout-demo",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    middleware=[Timeout(seconds=30)],
)
```

Because it only controls the wrapped call, `Timeout` works in both `middleware=` and `model_middleware=`. The deadline covers the complete call in the selected slot.
