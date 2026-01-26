import asyncio
import os
import random
import railtracks as rt  # adjust if your import path differs
from pydantic import BaseModel

class simple_output(BaseModel):
    output: str

SIMPLE_NODE = rt.agent_node(
    "Simple Terminal Agent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    output_schema=simple_output,
    system_message=rt.llm.SystemMessage("You are a helpful assistant. Keep responses short and to the point."),
)


async def run_once(n_tasks: int):
    prompts = [(i, "hello {i}") for i in range(n_tasks)]

    with rt.Session() as session:
        print("session id:", getattr(session, "_identifier", None))

        tasks = [rt.call(SIMPLE_NODE, p[1]) for p in prompts]
        # Note: do NOT use return_exceptions=True initially; we want it to fail loudly.
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    for i, res in enumerate(responses):
        if isinstance(res, Exception):
            print(f"TASK {i} failed: {res}")

    # Touch structured output (mirrors your evaluator)
    out = [(p[0], getattr(res, "structured", res)) for p, res in zip(prompts, responses)]
    return out


async def main():
    rounds = int(os.getenv("ROUNDS", "5"))
    n_tasks = int(os.getenv("N_TASKS", "100"))

    for r in range(rounds):
        # jitter helps trigger racey behavior
        await asyncio.sleep(random.random() * 0.05)
        print(f"\n--- round {r}/{rounds} (n_tasks={n_tasks}) ---")
        await run_once(n_tasks)


if __name__ == "__main__":
    asyncio.run(main())