If you are familiar and comfortable with the `async/await` syntax and you do not require any configurations, you can simply use the `railtracks.call` API to invoke your agent:
```python
import railtracks as rt

resp = await rt.call(AgentName, "user message to the agent")
```
!!! warning "async context"
    The above code snippet will work in an `async` context such as Jupyter notebooks. In a python script, it needs to be wrapped as follows:
    ```python
    from asyncio import run
    import railtracks as rt

    async def outer_func(...):
        resp = await rt.call(AgentName, "user message to the agent")

    run(outer_func(...))
    ```

The `call` API is also useful when you want to use agents as tools by having them wrapped within another a function (see [Agents as Tools]()). 

For configuration management such as context, observability through invocations, and other settings we recommend using [Flows]().