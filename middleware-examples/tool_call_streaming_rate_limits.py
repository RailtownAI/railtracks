import railtracks as rt
from aiolimiter import AsyncLimiter

limiter = AsyncLimiter(max_rate=1, time_period=1)  # Allow 1 call per second

summarizer = rt.agent_node(
    name="Summarizer Agent",
    system_message="You are a the purpose of a set of inputs and outputs into a single sentance. ",
    llm=rt.llm.OpenAILLM(model_name="gpt-4o"),
)



@rt.wrap_node
async def stream_inputs(call, *args, **kwargs):
    prompt = f"Please summarize the following inputs into a single sentence:\n\n{args}\n\n {kwargs}\n\n"
    input_response = await rt.call(summarizer, prompt)
    await rt.broadcast(input_response.content)

    try:
        return await call(*args, **kwargs)
    except Exception as e: 
        prompt = f"The tool failed to execute. Please summarize into a clean user facing statement. {e}"


    

@rt.wrap_node
async def rate_limit(call, *args, **kwargs):
    async with limiter:
        return await call(*args, **kwargs)


@rt.function_node
def add(a: int, b: int) -> int:
    """A simple function that adds two numbers."""
    return a + b



    