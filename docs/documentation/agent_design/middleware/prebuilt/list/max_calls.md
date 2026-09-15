# Max Calls

`Max Calls` is a middleware that limits the number of calls to a node or model. This can be useful if you want tools to be called just once per workflow, or in general if you want to limit the number of calls to a tool.

```python
--8<-- "docs/scripts/prebuilt_middleware.py:max_calls"
```

Because it only controls the wrapped call, `Max Calls` works in both
`middleware=` and `model_middleware=`. The limit is enforced on the complete call in
the selected slot.