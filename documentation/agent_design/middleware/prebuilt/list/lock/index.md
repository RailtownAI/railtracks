# Lock

`Lock` serializes concurrent invocations of a wrapped call. It is **slot-agnostic**, so it can protect either a whole node or an individual model call.

```python
import railtracks as rt
from railtracks.prebuilt.middleware import Lock

shared_lock = Lock()
LockedAgent = rt.agent_node(
    name="lock-demo",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    middleware=[shared_lock],
)
```

Reuse the same `Lock` instance on every node or model call that must not run at the same time. Separate instances do not block one another.
