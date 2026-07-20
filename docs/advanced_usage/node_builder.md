# Custom Node Creation with `NodeBuilder`

`NodeBuilder` is the internal factory behind `rt.agent_node` and `rt.function_node`. Those
helpers cover almost every case; reach for `NodeBuilder` directly only when you need to
assemble a node step by step. It is not part of the public API surface — import it from
`railtracks.built_nodes._node_builder`.

Every builder method returns a builder; call `.build()` to get the node class.

!!! note "Middleware lives in the middleware guide"
    `NodeBuilder.llm()` and `NodeBuilder.function()` take the same `middleware` /
    `model_middleware` parameters as the public helpers. See
    [Middleware](../documentation/agent_design/middleware/overview.md) for
    the full model — this page only shows where they attach.

---

## LLM nodes — `NodeBuilder.llm()`

```python
--8<-- "docs/scripts/node_builder.py:llm_basic"
```

Key parameters: `model` (a `ModelBase` **or** a no-arg factory returning one),
`system_message`, `schema`, `connected_nodes`, `tool_details` / `tool_params`,
`middleware`, `model_middleware`, and `context_injection`.

### Structured output

Pass a Pydantic model to `schema` and the node returns `StructuredResponse[YourModel]`
instead of `StringResponse`:

```python
--8<-- "docs/scripts/node_builder.py:llm_structured"
```

### Connected tools

`connected_nodes` lists the tools the agent may call:

```python
--8<-- "docs/scripts/node_builder.py:connected_tools"
```

### Exposing a node as a tool

Pass `tool_details` and `tool_params` to make the node callable as a tool from other
agents:

```python
--8<-- "docs/scripts/node_builder.py:expose_as_tool"
```

---

## Function nodes — `NodeBuilder.function()`

Wraps an async function as a node:

```python
--8<-- "docs/scripts/node_builder.py:function_node"
```

Sync functions are not supported directly — wrap them with `asyncio.to_thread` first.

---

## Middleware

Both builders accept `middleware` (around the node boundary, `wrapped_invoke`). LLM nodes
additionally accept `model_middleware` (around each raw model call, inside the
tool-calling loop). Each takes a `MiddlewareChain` or a bare list:

```python
--8<-- "docs/scripts/node_builder.py:middleware"
```

---

## Choosing the model at runtime

`model` accepts a no-arg factory as well as a concrete model. The factory is resolved
fresh on every model call, so the node can pick its model at invocation time:

```python
--8<-- "docs/scripts/node_builder.py:model_factory"
```

---

## Context injection

Context injection (filling `{placeholder}` templates from `rt.context`) is on by default
for all LLM nodes. Disable it per-node with `context_injection=False`:

```python
--8<-- "docs/scripts/node_builder.py:context_injection"
```

See the [Context Injection walkthrough](../tutorials/walkthroughs/prompts_and_context.md)
for the full four-level control hierarchy.
