"""Runnable examples for the prebuilt middleware docs.

Snippet regions (--8<-- [start:name]) are pulled into the prebuilt middleware
pages by MkDocs. Type-checked in CI via scripts/docs_validation.sh.
"""

from __future__ import annotations

# --8<-- [start: retry]
import railtracks as rt
from railtracks.prebuilt.middleware import Retry

# Retry is slot-agnostic: use it as node middleware, model middleware, or both.
RetryAgent = rt.agent_node(
    name="retry-demo",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    middleware=[Retry(3)],  # retry the whole node call
    model_middleware=[Retry(3)],  # retry each raw model call
)
# --8<-- [end: retry]


# --8<-- [start: retry_configured]
from railtracks.llm.retries import ExponentialRetry

# Tune the number of attempts, the backoff schedule, and which errors to retry.
picky_retry = Retry(
    approach=ExponentialRetry(max_tries=5),
    retry_on=(TimeoutError, ConnectionError),
)
# --8<-- [end: retry_configured]


# --8<-- [start: timeout]
import railtracks as rt
from railtracks.prebuilt.middleware import Timeout

TimedAgent = rt.agent_node(
    name="timeout-demo",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    middleware=[Timeout(seconds=30)],
)
# --8<-- [end: timeout]

# --8<-- [start: max_calls]
import railtracks as rt
from railtracks.prebuilt.middleware import MaxCalls, MaxCallsExceededError


def some_api_call() -> str:
    return "API response"


# MaxCalls is slot-agnostic: use it as node middleware, model middleware, or both.
LimitedApiCall = rt.function_node(
    some_api_call,
    middleware=[MaxCalls(max_calls=3, custom_message="API call budget exhausted")],
)


@rt.function_node
async def use_the_budget() -> list[str]:
    """Four calls against a budget that covers three."""
    results = []
    for _ in range(4):
        try:
            results.append(await rt.call(LimitedApiCall))
        except MaxCallsExceededError as exc:
            results.append(str(exc))
    return results


print(rt.Flow("max-calls-demo", entry_point=use_the_budget).invoke())
# ['API response', 'API response', 'API response', 'API call budget exhausted']
# --8<-- [end: max_calls]


# --8<-- [start: lock]
import railtracks as rt
from railtracks.prebuilt.middleware import Lock

shared_lock = Lock()
LockedAgent = rt.agent_node(
    name="lock-demo",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    middleware=[shared_lock],
)
# --8<-- [end: lock]


# --8<-- [start: context_injection]
import railtracks as rt
from railtracks.prebuilt.middleware import ContextInjection

# ContextInjection is model-level only. It fills {placeholders} in the prompt
# from the active session context before each model call.
CtxAgent = rt.agent_node(
    name="context-injection-demo",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are helping {user_name}. Keep answers short.",
    model_middleware=[ContextInjection()],
)

flow = rt.Flow(
    "ContextInjectionFlow",
    entry_point=CtxAgent,
    context={"user_name": "Alex"},
)
# flow.invoke("Who are you helping?")  ->  the model sees "You are helping Alex."
# --8<-- [end: context_injection]


# --8<-- [start: conversation_memory]
import railtracks as rt
from railtracks.prebuilt.middleware import ConversationMemory

# ConversationMemory is node-level: it preserves and appends conversation
# history across repeated invocations automatically.
memory = ConversationMemory()
ChatAgent = rt.agent_node(
    name="chat-demo",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    middleware=[memory],
)

flow = rt.Flow("ChatFlow", entry_point=ChatAgent)
# flow.invoke("What is your name?")
# flow.invoke("What did I just ask?")  -> Agent remembers Turn 1!
# --8<-- [end: conversation_memory]

