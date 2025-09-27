In this tutorial, we'll quickly cover how you can interact with any previous made agents in a multi-turn style chat.

Simply pass any of the agents you've made so far to the `interactive` method as follows:
```python
@rt.session
import asyncio
import railtracks as rt

ChatAgent = rt.agent_node(
    name="ChatAgent",
    system_message="You are a helpful assistant",
    llm=rt.llm.OpenAILLM("gpt-5"),
)


@rt.session
async def run():
    resp = await rt.interactive(
        ChatAgent,
    )


asyncio.run(run())
```
and you will see automatically a window pop open in your browser with the following style:
![Local Chat UI Example](../assets/local_chat/local_chat.png)

The possibilities from here on are endless. For instance you can replace the `llm` parameter with a locally running `Ollama` model and have your own locally run agent that you can chat with at your leisure! Give it tools to empower it even more.

```python
@rt.function_node
def some_super_secret_tool(secret_param1: int, secret_param2: str) -> str:
    """
    Secret tool capable of doing secret things

    Args:
        secret_param1: secret parameter
        secret_param2: secret parameter

    Returns:
        some super secret result
    """
    pass


@rt.session
import asyncio
import railtracks as rt

ChatAgent = rt.agent_node(
    name="ChatAgent",
    system_message="You are a helpful assistant",
    llm=rt.llm.OpenAILLM("gpt-5"),
)


@rt.session
async def run():
    resp = await rt.interactive(
        ChatAgent,
    )


asyncio.run(run())
```