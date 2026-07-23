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


# --8<-- [start: stream_callback]
# Passive session-wide listeners — neither enables streaming (only rt.astream does):
#   stream_callback    -> chunks from rt.broadcast_stream (LLM tokens included)
#   broadcast_callback -> one-off events from rt.broadcast (progress notes, ...)
observed_flow = rt.Flow(
    name="poet_observed",
    entry_point=agent,
    stream_callback=lambda chunk: print(chunk, end="", flush=True),
    broadcast_callback=lambda event: print(f"[event] {event}"),
)


async def main_observed():
    # tokens flow to stream_callback while the run streams; the broadcast_callback
    # only ever sees explicit rt.broadcast events (never the token chunks)
    final = await observed_flow.ainvoke("Write a short poem about rain.")
# --8<-- [end: stream_callback]
