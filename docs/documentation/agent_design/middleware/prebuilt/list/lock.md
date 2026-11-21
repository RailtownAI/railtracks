# Lock

`Lock` serializes concurrent invocations of a wrapped call. It is
**slot-agnostic**, so it can protect either a whole node or an individual model
call.

```python
--8<-- "docs/scripts/prebuilt_middleware.py:lock"
```

Reuse the same `Lock` instance on every node or model call that must not run at
the same time. Separate instances do not block one another.

`Lock` only serializes calls on the same event loop. Each sync `flow.invoke()` runs on its own loop, so two `invoke()` calls running at the same time on different threads are not serialized against each other.
