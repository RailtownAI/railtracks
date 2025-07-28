import railtracks as rt


def magic_number(x: int) -> int:
    """A simple tool that provides a magic number.
    Args:
        x (int): The number to be squared.
    Returns:
        int: The squared number.
    """

    return x * x

model = rt.llm.GeminiLLM(model_name="gemini-2.5-flash")
# model = rt.llm.OpenAILLM(model_name="gpt-4o")


terminal_agent = rt.library.terminal_llm(pretty_name="Terminal Agent",
                                         llm_model=model,
                                         system_message=rt.llm.SystemMessage("You are a helpful AI writing assistant."))

agent = rt.library.tool_call_llm(connected_nodes={magic_number},
                                 pretty_name="Magic Number Agent",
                                 llm_model=model,
                                 system_message=rt.llm.SystemMessage("You are a helpful AI writing assistant."))


# CALL 
# No runtime warnings errors for openai. error for : loop already closed
async def main():
    resp = await rt.call(agent, "Please give me the magic number for 5.")
    print(resp)
    
if __name__ == "__main__":
    import asyncio
    # asyncio.run(main())

# CALL SYNC
# working now after the change in call.py lines 272-274
resp = rt.call_sync(terminal_agent, "Please give me the magic number for 5.")
print(resp)

