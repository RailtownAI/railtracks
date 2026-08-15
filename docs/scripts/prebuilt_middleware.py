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
