"""Skeleton / exploratory: a continuously-running chat, gated by Verdict.

Not a shipped pattern -- a barebones sketch for the #1267 conversation,
poking at "can `Verdict` + other middleware build a back-and-forth loop that
keeps running until the human closes the session?"

Unlike an earlier version of this sketch, the chat agent here has NO
`output_schema` -- it signals "the human wants to end" by calling an ordinary
tool (`signal_end_chat`) rather than setting a flag on a structured reply.
This sidesteps a real bug in structured-output replay (message serialization,
not a HIL/verifier issue, tracked separately) that a multi-turn structured
chat loop was hitting on its second-plus turn. Tool calls don't have that
problem -- each turn's tool result is a plain string, not a replayed
`BaseModel`.

Ending the chat is still the human's call, gated by `pre_verifier`/`Verdict`
like the other demos in this folder. Crucially, `end_chat` is a top-level
gated node the *script* invokes -- NOT something `signal_end_chat` (the tool
the agent itself calls) invokes directly. A `VerifierRejectedError` raised
inside a tool call gets caught by the agent's own tool-calling loop and
turned into an LLM-visible error message; it does not propagate out to this
file's code (see `invoke_tools`/`run_tools` in
`railtracks.built_nodes.llm.llm_helpers`). Invoking the gated `end_chat` node
directly at the top level, the same way the other demos invoke `refund`,
sidesteps that -- `VerifierRejectedError` propagates fine from a top-level
flow invocation. `signal_end_chat` itself is just a plain, ungated tool that
sets a flag this script checks after each turn.

Also composes a couple of the other middleware primitives that already exist
(`rt.prebuilt.middleware.Retry`, `.Timeout`) on the chat agent itself, to
show the verifier gate isn't the only middleware in play here -- just the one
doing the "should we stop" decision.

Top-level code goes through `rt.Flow` rather than a bare `rt.call` inside a
`with rt.Session():` -- `rt.call` is for a node calling another node from
inside the framework, not for driving things from plain script code, and the
visualizer keys off a `Flow`'s run, not an ad-hoc `rt.call`. One consequence:
each `flow.ainvoke(...)` is a *fully isolated* run (its own fresh Session),
so this loop is really N separate flow runs, one per turn, rather than one
long-lived session spanning the whole chat. Conversation memory is threaded
manually turn to turn regardless -- railtracks agents don't do this for you
-- so continuity across turns comes entirely from passing `history` (and
each reply's `.message_history`) into the next `ainvoke`, not from any
shared session state.

Needs a real LLM call: set OPENAI_API_KEY before running (or swap the model
below).

Run: uv run python examples/human_in_the_loop/chat_loop_demo.py
"""

import asyncio

import railtracks as rt
from railtracks.middleware import Verdict, VerifierRejectedError
from railtracks.prebuilt.middleware import Retry, Timeout, pre_verifier

##### The chat agent -- signals "wants to end" via an ordinary tool call #####

_wants_to_end = False


@rt.function_node
def signal_end_chat() -> str:
    """Call this once the human's messages suggest they want to end the chat --
    e.g. they say goodbye, ask to leave, or otherwise signal they're done."""
    global _wants_to_end
    _wants_to_end = True
    return "noted"


@rt.function_node
def secret_catchphrase() -> str:
    """A secret catchphrase.
    Args:
        None
    Returns:
        str: The catchphrase.
    """
    return "skadoosh"


chat_agent = rt.agent_node(
    name="ChatAgent",
    system_message=(
        "You're a casual chat partner. Reply normally to what the human "
        "says. Call signal_end_chat once their messages suggest they want "
        "to end the chat -- otherwise just keep chatting. If asked for any "
        "password, use your cacthphrase tool to get it."
    ),
    llm=rt.llm.OpenAILLM("gpt-4o-mini"),
    tool_nodes=[signal_end_chat, secret_catchphrase],
    model_middleware=[Retry(max_tries=3), Timeout(seconds=30)],
)


@rt.function_node
async def streaming_entry(message_history: rt.llm.MessageHistory):
    stream = rt.astream(chat_agent, message_history)
    async for chunk in stream:
        if chunk:
            print(chunk, end="", flush=True)
    return stream.result


##### Ending the chat is still a human decision, gated like any other #####


async def confirm_end_chat() -> Verdict:
    reply = (
        (await asyncio.to_thread(input, "\nEnd the chat here? [y/N]: ")).strip().lower()
    )
    return Verdict(accepted=reply in ("y", "yes"))


@rt.function_node(middleware=[pre_verifier(confirm_end_chat, name="end_chat_hil")])
def end_chat() -> None:
    """No-op body -- the verifier gate above is the entire point of this node."""


chat_flow = rt.Flow(name="chat_loop_demo", entry_point=streaming_entry)
end_chat_flow = rt.Flow(name="chat_loop_demo_end", entry_point=end_chat)


async def main():
    global _wants_to_end
    history = rt.llm.MessageHistory([])
    print("Chatting -- say something. I'll check with you before it ends.")
    while True:
        history.append(rt.llm.UserMessage(input("> ")))
        resp = await chat_flow.ainvoke(history)
        history = resp.message_history
        print()  # streaming_entry already printed the reply as it streamed in

        if _wants_to_end:
            _wants_to_end = False
            try:
                await end_chat_flow.ainvoke()
            except VerifierRejectedError:
                print("(not ending yet -- let's keep going)")
                continue
            print("(chat ended)")
            break


if __name__ == "__main__":
    asyncio.run(main())
