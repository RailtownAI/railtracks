# --8<-- [start: astream_basic]
import railtracks as rt

agent = rt.agent_node(
    name="Poet",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a concise poet.",
)


async def main():
    stream = rt.astream(agent, user_input="Write a short poem about rain.")

    async for chunk in stream:
        print(chunk, end="", flush=True)  # str token chunks

    final = stream.result  # the complete StringResponse
# --8<-- [end: astream_basic]


# --8<-- [start: astream_await]
async def main_await():
    # when you only care about the final result of the streamed run
    final = await rt.astream(agent, user_input="Write a short poem about rain.")
# --8<-- [end: astream_await]


# --8<-- [start: astream_nested]
# rt.astream targets an agent node; use it inside a @function_node and drive the
# outer node with rt.call. Each stream is independent, so concurrent streams simply
# have their own handles.
@rt.function_node
async def head(prompt: str) -> str:
    stream = rt.astream(agent, user_input=prompt)
    async for chunk in stream:
        print(chunk, end="", flush=True)
    return stream.result.text


async def main_nested():
    # the function node is buffered (rt.call); only the agent inside it streams
    text = await rt.call(head, "Write a short poem about rain.")
# --8<-- [end: astream_nested]
