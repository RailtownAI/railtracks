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
except NodeInvocationError as e:
    if e.fatal:
        # Fatal errors should stop execution
        logger.error(f"Fatal node error: {e}")
        raise
    else:
        # Non-fatal errors can be handled gracefully
        logger.warning(f"Node error (recoverable): {e}")
        # Implement retry logic or fallback
        
except LLMError as e:
    logger.error(f"LLM operation failed: {e.reason}")
    # Maybe retry with different parameters
    # Or fallback to a simpler approach
# --8<-- [end: simple_handling]

# --8<-- [start: comprehensive_handling]
from railtracks.exceptions import (
    NodeCreationError, NodeInvocationError, 
    LLMError, GlobalTimeOutError, ContextError, FatalError
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
    
except NodeInvocationError as e:
    # Runtime execution issue
    if e.fatal:
        logger.error("Fatal execution error - stopping")
        raise
    else:
        logger.warning("Recoverable execution error")
        # Implement recovery strategy
        
except LLMError as e:
    # LLM-specific issue
    logger.error(f"LLM error: {e.reason}")
    if e.message_history:
        # Analyze conversation for debugging
        pass
        
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
from railtracks.exceptions import NodeInvocationError, NodeCreationError

async def call_with_retry(node, user_input, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await rt.call(node, user_input=user_input)
        except (NodeInvocationError, LLMError) as e:
            if attempt == max_retries - 1:
                raise  # Last attempt, re-raise
            
            wait_time = 2 ** attempt  # Exponential backoff
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s")
            await asyncio.sleep(wait_time)
# --8<-- [end: exp_backoff]

# --8<-- [start: fallback]
from railtracks.exceptions import NodeInvocationError

async def call_with_fallback(primary_node, fallback_node, user_input):
    try:
        return await rt.call(primary_node, user_input=user_input)
    except NodeInvocationError as e:
        if not e.fatal:
            logger.info("Primary execution failed, trying fallback")
            return await rt.call(fallback_node, user_input=user_input)
        raise
# --8<-- [end: fallback]



