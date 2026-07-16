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
    print("\n\nfinal:", final.text)
# --8<-- [end: astream_basic]


# --8<-- [start: astream_await]
async def main_await():
    # when you only care about the final result of the streamed run
    final = await rt.astream(agent, user_input="Write a short poem about rain.")
    print(final.text)
# --8<-- [end: astream_await]


# --8<-- [start: flow_astream]
flow = rt.Flow(name="poet_flow", entry_point=agent)


async def main_flow():
    stream = flow.astream("Write a short poem about rain.")

    async for chunk in stream:
        print(chunk, end="", flush=True)

    final = stream.result
# --8<-- [end: flow_astream]


# --8<-- [start: route]
def on_chunk(chunk: str) -> None:
    print(chunk, end="", flush=True)


async def main_push():
    # push-style consumption of ONE streamed call: route() dispatches chunks to handlers
    # by channel and returns the final result. route() is what enables the streaming.
    push_flow = rt.Flow(name="poet_push", entry_point=agent)
    result = await push_flow.astream("Write a poem.").route(on_chunk)
    print("\n\nresult:", result.text)

    # dict form routes per channel (unregistered channels are skipped)
    result = await push_flow.astream("Write a poem.").route({"default": on_chunk})
# --8<-- [end: route]


# --8<-- [start: broadcast_callback]
# a PASSIVE session-wide listener: receives every broadcast item of the flow's runs but
# never enables streaming. Prefer the dict form; if it never fires, a warning is logged.
observer_flow = rt.Flow(
    name="poet_observed",
    entry_point=agent,
    broadcast_callback={
        "progress": lambda item: print(f"[progress] {item}"),
    },
)


async def main_observed():
    result = await observer_flow.ainvoke("Write a poem.")  # buffered; only explicit
    return result                                          # rt.broadcast items observed
# --8<-- [end: broadcast_callback]


# --8<-- [start: custom_node]
from railtracks.llm import UserMessage

model = rt.llm.OpenAILLM("gpt-4o-mini")


@rt.function_node
async def poem(topic: str) -> str:
    # forward the model stream to whoever is consuming this run; if nobody is
    # listening the chunks are dropped and this behaves like a buffered call.
    response = await rt.broadcast_stream(
        model.astream_chat([UserMessage(f"Write a short poem about {topic}.")])
    )
    return response.text


async def main_custom():
    stream = rt.astream(poem, topic="sunshine")
    async for chunk in stream:
        print(chunk, end="", flush=True)
    final = stream.result  # the node's return value (str here)
# --8<-- [end: custom_node]


# --8<-- [start: custom_channels]
@rt.function_node
async def two_streams(topic: str) -> str:
    draft = await rt.broadcast_stream(
        model.astream_chat([UserMessage(f"Draft a poem about {topic}.")]),
        channel="draft",
    )
    final = await rt.broadcast_stream(
        model.astream_chat([UserMessage(f"Polish this poem:\n{draft.text}")]),
        channel="final",
    )
    return final.text


async def main_two_streams():
    # only consume the "final" channel; "draft" chunks are ignored
    stream = rt.astream(two_streams, topic="sunshine").on_channel("final")
    async for chunk in stream:
        print(chunk, end="", flush=True)
# --8<-- [end: custom_channels]


# --8<-- [start: agent_stream_channel]
writer = rt.agent_node(
    name="Writer",
    llm=rt.llm.OpenAILLM("gpt-4o-mini"),
    system_message="Write prose.",
    stream_channel="writer",     # this agent's tokens are emitted on the «writer» bus
)

critic = rt.agent_node(
    name="Critic",
    llm=rt.llm.OpenAILLM("gpt-4o-mini"),
    system_message="Critique prose.",
    stream_channel="critic",     # ...and this one's on the «critic» bus
)


@rt.function_node
async def review_pipeline(topic: str) -> str:
    # nested rt.call would run buffered (frame-local rule); nested rt.astream opts each
    # child into streaming — its tokens flow to the bus named by its stream_channel.
    draft = await rt.astream(writer, user_input=f"Write about {topic}.")
    review = await rt.astream(critic, user_input=draft.text)
    return review.text


# a passive broadcast_callback observes ALL scopes in the session — including the
# nested astream scopes created inside the pipeline (route() would only see the entry
# scope, so the multi-agent fan-out uses the session-wide listener instead)
routed_flow = rt.Flow(
    name="review",
    entry_point=review_pipeline,
    broadcast_callback={
        "writer": lambda c: print(c, end="", flush=True),   # writer tokens → pane 1
        "critic": lambda c: print(f"\x1b[2m{c}\x1b[0m", end="", flush=True),  # critic → pane 2
    },
)
# --8<-- [end: agent_stream_channel]


# --8<-- [start: get_stream]
import asyncio


@rt.function_node
async def token_source(topic: str) -> str:
    # a child that explicitly streams its tokens onto the "tokens" channel
    return (
        await rt.broadcast_stream(
            model.astream_chat([UserMessage(f"Write two lines about {topic}.")]),
            channel="tokens",
        )
    ).text


@rt.function_node
async def orchestrator(topic: str) -> str:
    # run the producer concurrently and fold its live tokens in from the channel
    task = asyncio.create_task(rt.call(token_source, topic=topic))
    collected = ""
    # default streams=1: ends by itself once one production completes on the channel
    async for chunk in rt.context.get_stream("tokens"):
        print(chunk, end="", flush=True)
        collected += chunk
    return await task
# --8<-- [end: get_stream]


# --8<-- [start: model_astream]
async def main_model():
    # model-level streaming, outside any node/session
    final_response = None  # seed so it is always bound (a stream could be empty)
    async for item in model.astream_chat([UserMessage("Tell me who you are.")]):
        if isinstance(item, str):
            print(item, end="", flush=True)  # token chunk
        else:
            final_response = item  # the terminal Response (with usage info)
    assert final_response is not None
# --8<-- [end: model_astream]
