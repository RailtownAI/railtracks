# Fallback

`Fallback` hands the input to backup nodes, in order, when the wrapped node raises an error covered by `on` — `LLMError` by default. It routes between **nodes**, not models: every attempt is a real node run through `rt.call`, so each backup is recorded in the session like any other node. The common case is an agent whose model is unreliable (a small on-device model, a provider outage, rate limits), where the backups are the same agent built on other models.

It is **node-level**: attach it on `middleware=`, not `model_middleware=`.

## Usage

```python
--8<-- "docs/scripts/prebuilt_middleware.py:fallback"
```

!!! note "Each attempt starts fresh"
    A backup starts from the original input; it does not see the primary's partial work, so any tools the primary already ran will run again. Backups must accept the same input as the wrapped node.

By default only `LLMError` triggers a fallback. Pass `on=` to widen or narrow the trigger set, like `Retry`'s `retry_on`; anything not in the tuple propagates immediately. Re-entering the same `Fallback` instance from inside one of its own attempts (a backup that carries it, or two instances pointed at each other) runs the node plainly instead of looping forever.

!!! note "Budgets"
    A `MaxCalls` instance shared between the primary and its backups counts every attempt against the same budget; a fresh `MaxCalls` per agent gives each its own.
