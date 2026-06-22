# Key-Value Memory Tooling
A common addition to your agent is a place to remember facts and read them back later — the user's timezone, a project deadline, a preference. Railtracks provides a built-in key-value memory tool you can drop into your agent right away.

## Usage
Adding the memory tool to your agent is super easy.

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory"
```

!!! Warning
    Memory is scoped to the `KeyValueMemoryToolSet` instance — all tools returned from the same instance share one namespace. To keep separate memories for different agents, create a separate `KeyValueMemoryToolSet` (with its own store) for each.

You will usually want to tell the agent how to use memory in your prompt. We provide a helper that returns a ready-made guidance string:

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory_prompt"
```

## The Tools

The toolset exposes five tools to the agent:

| Tool | Purpose |
|---|---|
| `remember(key, value)` | Save a fact under a key. Re-calling with the same key overwrites the value, so keys should be short and stable (e.g. `user_timezone`). |
| `recall(key)` | Read back the value stored under a key, or a clear "not found" message. |
| `forget(key)` | Delete the fact under a key. Forgetting an absent key is a reported no-op. |
| `list_keys()` | List just the stored keys, without their values — cheaper on context than `list_memories()` when the agent only needs to see what exists. |
| `list_memories()` | List every stored `key: value` pair. |
| `search_memories(query)` | Find entries by case-insensitive substring across keys and values — useful when the agent recalls roughly what a fact was about but not the exact key. |

## Persistence

By default the toolset uses a fresh in-process store, so memory lasts only for the life of the object. To persist memory across runs, pass an `InMemoryKeyValueStore` constructed with a `snapshot_path` — the store loads from that file on startup and flushes to it after every change, with no external dependencies.

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory_persistent"
```

The `store` argument accepts any object implementing the
[`KeyValueStore`][railtracks.retrieval.stores.key_value.KeyValueStore] protocol,
so you can supply your own backend (a database, Redis, etc.) without changing
the toolset.

## Connecting memory to a larger system

The `on_change` callback fires after every mutation, letting the outer system react in real time — push to a UI, mirror to a database, or trigger a notification. It is called as `on_change(key, value)`, where `value` is the new value on a save and `None` on a forget.

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory_callback"
```

You can also inspect memory directly at any point via the toolset's `store` —
useful for logging, assertions, or driving downstream logic once the agent
finishes. The store is async:

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory_inspection"
```
