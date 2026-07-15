# Key-Value Memory Tooling
A common addition to your agent is a place to remember facts and read them back later: the user's timezone, a project deadline, a preference. Railtracks provides a built-in key-value memory tool you can drop into your agent right away.

## Usage
Adding the memory tool to your agent is super easy.

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory"
```

!!! Warning
    Memory is scoped to the `KeyValueMemoryToolSet` instance. All tools returned from the same instance share one namespace. To keep separate memories for different agents, create a separate `KeyValueMemoryToolSet` (with its own store) for each.

You will usually want to tell the agent how to use memory in your prompt. We provide a helper that returns a ready-made guidance string:

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory_prompt"
```

## The Tools

The toolset exposes six tools to the agent:

| Tool | Purpose |
|---|---|
| `remember(key, value)` | Save a fact under a key. Re-calling with the same key overwrites the value, so keys should be short and stable (e.g. `user_timezone`). |
| `recall(key)` | Read back the value stored under a key, or a clear "not found" message. |
| `forget(key)` | Delete the fact under a key. Forgetting an absent key is a reported no-op. |
| `list_keys()` | List just the stored keys, without their values — cheaper on context than `list_memories()` when the agent only needs to see what exists. |
| `list_memories()` | List every stored `key: value` pair. |
| `search_memories(query)` | Rank stored entries by relevance to a free-text query across keys and values; useful when the agent recalls roughly what a fact was about but not the exact key. See [Searching memory](#searching-memory). |

## Searching memory

When the agent knows roughly *what* a fact was about but not the exact key, it calls `search_memories(query)`. The ranking behind that tool is pluggable via the `search` argument, so you choose how matches are found without changing anything else.

**Lexical (default).** Uses `LexicalSearch`; a pure, zero-dependency word-matching ranker. It scores each entry by how well the query overlaps its key and value, with the key weighted more heavily (an exact key match wins outright), rewards multi-word queries that match more terms, and has a fuzzy fallback that tolerates typos. It needs no configuration and no network calls. You can tune its scoring weights if a corpus needs it:

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory_search_lexical"
```

**Semantic (opt-in).** For matching by *meaning* rather than shared words. Pass a `SemanticSearch`, which ranks entries by embedding similarity. It embeds your memories with the `Embedding` you supply and keeps a vector index in sync as memories change (only new or edited entries are re-embedded). This pulls in an embedding provider and the vector backend, so it is opt-in rather than the default.

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory_search_semantic"
```

Both satisfy the same `SearchAlgorithm` protocol, so you can also supply your own ranking strategy (e.g. a hybrid of the two) by implementing that one method.

## Persistence

By default the toolset uses a fresh in-process store, so memory lasts only for the life of the object. To persist memory across runs, pass an `InMemoryKeyValueStore` constructed with a `snapshot_path` the store loads from that file on startup and flushes to it after every change, with no external dependencies.

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory_persistent"
```

The `store` argument accepts any object implementing the
`KeyValueStore` protocol,
so you can supply your own backend (a database, Redis, etc.) without changing the toolset.

## Connecting memory to a larger system

The `on_change` callback fires after every mutation, letting the outer system react in real time  (push to a UI, mirror to a database, or trigger a notification). It is called as `on_change(key, value)`, where `value` is the new value on a save and `None` on a forget.

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory_callback"
```

You can also inspect memory directly at any point via the toolset's `store`; useful for logging, assertions, or driving downstream logic once the agent finishes. The store is async:

```python
--8<-- "docs/scripts/key_value_memory.py:kv_memory_inspection"
```
