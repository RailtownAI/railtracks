# --8<-- [start: wrappers]
import railtracks as rt


@rt.wrap_node
async def retry(call, *args, **kwargs):
    """Retry the inner call up to 3 times."""
    last = None
    for _ in range(3):
        try:
            return await call(*args, **kwargs)
        except Exception as e:
            last = e

    raise RuntimeError(f"All retries exhausted: {last}") from last

# you can add the middleware to a node at creation time.
RetryAgent = rt.agent_node(name="Agent", llm=rt.llm.OpenAILLM("gpt-4o"), middleware=[retry])
# --8<-- [end: wrappers]


# --8<-- [start: wrappers_timed]
@rt.wrap_node
async def timed(call, *args, **kwargs):
    import time

    start = time.perf_counter()
    result = await call(*args, **kwargs)
    print(f"[timed] {(time.perf_counter() - start) * 1000:.1f} ms")
    return result
# --8<-- [end: wrappers_timed]


# --8<-- [start: after_node_demo]
@rt.after_node
def log_result(result):
    print("node finished:", result)
    return result


@rt.wrap_node
async def log_result_async(call, *args, **kwargs):
    result = await call(*args, **kwargs)
    print("node finished:", result)
    return result
# --8<-- [end: after_node_demo]


# --8<-- [start: model_middleware_demo]
@rt.before_llm
def print_message(message_history: rt.llm.MessageHistory, schema, tools):
    print(message_history)
    return message_history, schema, tools


@rt.after_llm
def print_response(response: rt.llm.Response):
    print(response.message)
    return response


@rt.wrap_llm
async def periodic_failure(llm_call, message_history, schema, tools):
    import random

    if random.random() < 0.5:
        raise Exception("Random failure")
    return await llm_call(message_history, schema, tools)
# --8<-- [end: model_middleware_demo]


# --8<-- [start: attach_creation]
CreationTimeAgent = rt.agent_node(
    name="Agent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    middleware=[retry, log_result],  # runs once per agent call
    model_middleware=[print_message, print_response],  # runs once per model call
)
# --8<-- [end: attach_creation]


# --8<-- [start: attach_after_creation]
BaseAgent = rt.agent_node(name="Agent", llm=rt.llm.OpenAILLM("gpt-4o"))

# extend_middleware returns a NEW Node subclass; BaseAgent itself is untouched.
ExtendedAgent = BaseAgent.extend_middleware(retry, log_result)
# --8<-- [end: attach_after_creation]


# --8<-- [start: ordering_demo]
@rt.wrap_node
async def outer(call, *args, **kwargs):
    print("outer: before")
    result = await call(*args, **kwargs)
    print("outer: after")
    return result


@rt.wrap_node
async def inner(call, *args, **kwargs):
    print("inner: before")
    result = await call(*args, **kwargs)
    print("inner: after")
    return result


OrderedAgent = rt.agent_node(
    name="Agent", llm=rt.llm.OpenAILLM("gpt-4o"), middleware=[outer, inner]
)
# calling OrderedAgent prints, in order:
#   outer: before
#   inner: before
#   inner: after
#   outer: after
# --8<-- [end: ordering_demo]



# --8<-- [start: prebuilt_model_middleware_demo]
from railtracks.prebuilt.guardrails import PIIRedactInputGuard, PIIRedactOutputGuard

GuardedAgent = rt.agent_node(
    name="pii-redact-demo",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a concise assistant.",
    model_middleware=[PIIRedactInputGuard(), PIIRedactOutputGuard()],
)
# --8<-- [end: prebuilt_model_middleware_demo]
