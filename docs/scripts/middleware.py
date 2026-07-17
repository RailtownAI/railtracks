"""Runnable snippets for the Middleware docs.

Each named region (start/end markers below) is embedded into a docs page via
pymdownx.snippets. The file reads top-to-bottom: helpers defined in an early
region (e.g. `retry`, `normalize`) are reused by later ones, matching the order
the usage guide presents them.
"""

# --8<-- [start: wrappers]
import railtracks as rt


@rt.wrapper
async def retry(call, *args, **kwargs):
    """Retry the inner call up to 3 times."""
    last = None
    for _ in range(3):
        try:
            return await call(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


@rt.wrapper
async def timed(call, *args, **kwargs):
    import time

    start = time.perf_counter()
    result = await call(*args, **kwargs)
    print(f"[timed] {(time.perf_counter() - start) * 1000:.1f} ms")
    return result
# --8<-- [end: wrappers]


_CACHE: dict = {}


# --8<-- [start: wrapper_cached]
@rt.wrapper
async def cached(call, *args, **kwargs):
    key = (args, tuple(sorted(kwargs.items())))
    if key in _CACHE:
        return _CACHE[key]  # inner call never runs
    result = await call(*args, **kwargs)
    _CACHE[key] = result
    return result
# --8<-- [end: wrapper_cached]


# --8<-- [start: entry_gate]
@rt.gate
async def normalize(text: str):
    return (text.strip().lower(),)  # tuple -> positional args only


@rt.gate
async def route(city: str):
    return {"city": city, "units": "metric"}  # dict -> keyword args only


@rt.gate
async def reorder(a, b):
    return rt.gate.args(b, a, flag=True)  # both -> ((b, a), {"flag": True})
# --8<-- [end: entry_gate]


# --8<-- [start: exit_gate]
@rt.gate
async def add_banner(result: str):
    return f">>> {result} <<<"


@rt.gate
async def audit(result):
    print(f"produced {result!r}")  # returns None -> result unchanged
# --8<-- [end: exit_gate]


# --8<-- [start: gate_guardrail]
@rt.gate
async def no_secrets(text: str):
    if "password" in text.lower():
        raise ValueError("blocked: input mentions a secret")
    # returns None -> the call proceeds unchanged
# --8<-- [end: gate_guardrail]


# --8<-- [start: gate_direct_call]
@rt.gate
def tag(x):
    return f"[{x}]"


tag("hi")  # -> '[hi]'  (raw function result)
# --8<-- [end: gate_direct_call]


# --8<-- [start: middlewarechain_bands]
ms = rt.MiddlewareChain(
    wrappers=[retry],  # outermost: wrap the whole call
    entry_gate=[normalize],  # transform input (before the core)
    exit_gate=[add_banner],  # transform output (after the core)
    inner_wrappers=[cached],  # innermost: hug the core, inside the gateways
)
# --8<-- [end: middlewarechain_bands]


# --8<-- [start: bare_list]
# retry -> wrappers, no_secrets -> entry_gate
middleware = [retry, no_secrets]
# --8<-- [end: bare_list]


# --8<-- [start: raw_in_slots]
async def add_marker(text):  # raw async function, no @rt.gate
    return (f"[{text}]",)


def shout(result):  # raw *sync* function (gateways may be sync)
    return result.upper()


raw_ms = rt.MiddlewareChain(entry_gate=[add_marker], exit_gate=[shout])
# --8<-- [end: raw_in_slots]


# --8<-- [start: attach_function_node]
echo = rt.function_node(
    lambda text: f"echo: {text}",
    name="echo",
    middleware=rt.MiddlewareChain(entry_gate=[normalize], exit_gate=[add_banner]),
)
# --8<-- [end: attach_function_node]


# --8<-- [start: attach_function_decorator]
@rt.function_node(middleware=[no_secrets])
async def lookup(user_id: str):
    ...
# --8<-- [end: attach_function_decorator]


# --8<-- [start: attach_agent]
assistant = rt.agent_node(
    name="Mentor",
    llm=rt.llm.OpenAILLM("gpt-4o-mini"),
    system_message="Answer in one sentence.",
    middleware=[no_secrets],  # node boundary: once per agent call
    model_middleware=rt.MiddlewareChain(entry_gate=[normalize]),  # each model call
)
# --8<-- [end: attach_agent]


# --8<-- [start: model_source]
def pick_model():
    # Resolved fresh on every model call — choose from config, rt.context, etc.
    return rt.llm.OpenAILLM(rt.context.get("model_name") or "gpt-4o-mini")


dynamic_agent = rt.agent_node(
    name="Dynamic",
    llm=pick_model,  # a no-arg factory in place of a concrete model
    system_message="Answer concisely.",
)
# --8<-- [end: model_source]


# --8<-- [start: end_to_end]
import re


@rt.wrapper
async def retry_run(call, *args, **kwargs):
    for attempt in range(3):
        try:
            return await call(*args, **kwargs)
        except Exception:
            if attempt == 2:
                raise


@rt.gate
async def hide_secrets(text: str):
    found = re.findall(r"\b[A-Za-z0-9]{10,}\b", text)
    rt.context.put("secrets", found)
    return (re.sub(r"\b[A-Za-z0-9]{10,}\b", "[SECRET]", text),)  # tuple -> positional


@rt.gate
async def restore_secrets(result):
    text = result.content if hasattr(result, "content") else result
    for s in rt.context.get("secrets") or []:
        text = text.replace("[SECRET]", s, 1)
    return text


secret_agent = rt.agent_node(
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="Echo [SECRET] tokens back verbatim.",
    middleware=rt.MiddlewareChain(
        wrappers=[retry_run],
        entry_gate=[hide_secrets],
        exit_gate=[restore_secrets],
    ),
)
# --8<-- [end: end_to_end]
