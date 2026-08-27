import railtracks as rt


@rt.function_node
async def func(user_input: str):
    pass


# --8<-- [start: fatal_error]
def critical_function():
    from railtracks.exceptions import FatalError

    raise FatalError("A critical error occurred.")


# --8<-- [end: fatal_error]

# --8<-- [start: simple_handling]
from railtracks.exceptions import NodeInvocationError, LLMError
import logging

logger = logging.getLogger(__name__)

try:
    result = await rt.call(func, "Tell me about machine learning")

# LLMError is a NodeInvocationError, so it must come first -- Python takes the
# first *matching* clause, not the most specific one.
except LLMError as e:
    logger.error(f"LLM operation failed: {e.reason}")
    # Maybe retry with different parameters, or fall back to a simpler approach

except NodeInvocationError as e:
    if e.fatal:
        # Fatal errors should stop execution
        logger.error(f"Fatal node error: {e}")
        raise
    else:
        # Non-fatal errors can be handled gracefully
        logger.warning(f"Node error (recoverable): {e}")
        # Implement retry logic or fallback
# --8<-- [end: simple_handling]

# --8<-- [start: llm_dispatch]
from railtracks.exceptions import (
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMError,
    NodeInvocationError,
)

try:
    result = await rt.call(func, "Summarise this document")

except LLMTimeoutError:
    # The model did not answer in time -- usually worth another attempt.
    result = await rt.call(func, "Summarise this document")

except LLMRateLimitError:
    # Back off rather than hammering the provider.
    await asyncio.sleep(30)
    result = await rt.call(func, "Summarise this document")

except LLMAuthenticationError:
    # Retrying will never help; this is a configuration problem.
    logger.critical("Check your API key")
    raise

except LLMError as e:
    # Any other LLM failure. The provider's original error is on __cause__.
    logger.error(f"LLM failed: {e.reason} (cause: {e.__cause__!r})")
    raise

except NodeInvocationError as e:
    # The node died for a non-LLM reason -- config, guardrail, structure.
    logger.error(f"Node failed: {e}")
    raise
# --8<-- [end: llm_dispatch]

# --8<-- [start: comprehensive_handling]
from railtracks.exceptions import (
    NodeCreationError,
    NodeInvocationError,
    LLMError,
    GlobalTimeOutError,
    ContextError,
    FatalError,
)

try:
    # Setup phase
    node = rt.agent_node(
        llm=rt.llm.OpenAILLM("gpt-4o"),
        system_message="You are a helpful assistant",
    )

    # Configure timeout
    rt.set_config(timeout=60.0)

    # Execution phase
    result = await rt.call(node, user_input="Explain quantum computing")

except NodeCreationError as e:
    # Configuration or setup issue
    logger.error("Node setup failed - check your configuration")
    print(e)  # Shows debugging tips

except LLMError as e:
    # LLM-specific issue. Listed above NodeInvocationError because it is one.
    logger.error(f"LLM error: {e.reason}")
    if e.message_history:
        # Analyze conversation for debugging
        pass

except NodeInvocationError as e:
    # Runtime execution issue that did not come from the LLM
    if e.fatal:
        logger.error("Fatal execution error - stopping")
        raise
    else:
        logger.warning("Recoverable execution error")
        # Implement recovery strategy

except GlobalTimeOutError as e:
    # Execution took too long
    logger.error(f"Execution timed out after {e.timeout}s")
    # Maybe increase timeout or optimize graph

except ContextError as e:
    # Context management issue
    logger.error("Context error - check your context setup")
    print(e)  # Shows debugging tips

except FatalError as e:
    # User-defined critical error
    logger.critical(f"Fatal error: {e}")
    # Implement emergency shutdown procedures

except Exception as e:
    # Non-RT errors
    logger.error(f"Unexpected error: {e}")

# --8<-- [end: comprehensive_handling]

# --8<-- [start: exp_backoff]
import asyncio
import railtracks as rt
from railtracks.exceptions import LLMRateLimitError, LLMTimeoutError

# Retry only what is actually transient. A malformed tool or a bad API key fails the
# same way every time, so retrying those just delays the error you need to see.
RETRYABLE = (LLMTimeoutError, LLMRateLimitError)


async def call_with_retry(node, user_input, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await rt.call(node, user_input=user_input)
        except RETRYABLE as e:
            if attempt == max_retries - 1:
                raise  # Last attempt, re-raise

            wait_time = 2**attempt  # Exponential backoff
            logger.warning(f"{type(e).__name__}, retrying in {wait_time}s")
            await asyncio.sleep(wait_time)


# --8<-- [end: exp_backoff]

# --8<-- [start: fallback]
from railtracks.exceptions import LLMError


async def call_with_fallback(primary_node, fallback_node, user_input):
    try:
        return await rt.call(primary_node, user_input=user_input)
    except LLMError:
        # The model let us down; a different one may not.
        logger.info("Primary execution failed, trying fallback")
        return await rt.call(fallback_node, user_input=user_input)


# --8<-- [end: fallback]


# --8<-- [start: custom_node]
import railtracks as rt
from railtracks.exceptions import LLMRateLimitError, LLMTimeoutError, LLMError

cheap = rt.agent_node(llm=rt.llm.OpenAILLM("gpt-4o-mini"), name="Cheap")
strong = rt.agent_node(llm=rt.llm.AnthropicLLM("claude-sonnet-4-5"), name="Strong")


@rt.function_node
async def summarise(user_input: str) -> str:
    """Summarise text, degrading gracefully as things go wrong."""
    try:
        return (await rt.call(cheap, user_input)).content

    except LLMTimeoutError:
        # Slow model, not a broken one -- a second attempt often lands.
        return (await rt.call(cheap, user_input)).content

    except LLMRateLimitError:
        # Rate limited on the cheap tier; spend money instead of waiting.
        return (await rt.call(strong, user_input)).content

    except LLMError as e:
        # Anything else from the LLM: give the caller something usable, and keep the
        # provider's original error attached for the logs.
        logger.warning("Summarisation failed: %s (cause: %r)", e.reason, e.__cause__)
        return "Summary unavailable."


# --8<-- [end: custom_node]
