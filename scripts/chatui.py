import asyncio
import sys

import railtracks as rt


# --8<-- [start: interactive]
@rt.function_node
def programming_language_info(language: str) -> str:
    """
    Returns the version of the specified programming language

    Args:
        language (str): The programming language to get the version for. Supported values are "python".
    """
    if language == "python":
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return "Unknown language"


ChatAgent = rt.agent_node(
    name="ChatAgent",
    system_message="You are a helpful assistant",
    llm=rt.llm.OpenAILLM("gpt-5"),
    tool_nodes=[programming_language_info],
)


async def main():
    response = await rt.interactive.local_chat(ChatAgent)
    print(response.content)


# --8<-- [end: interactive]

# --8<-- [start: advanced]
AnalysisAgent = rt.agent_node(
    name="AnalysisAgent",
    system_message="You are a helpful assistant that analyzes customer interactions with agents",
    llm=rt.llm.OpenAILLM("gpt-5"),
)


async def analysis():
    response = await rt.interactive.local_chat(ChatAgent)

    analysis_response = await rt.call(
        AnalysisAgent,
        f"Analyze the following conversation and provide a summary in less than 10 words:\n\n{response.message_history}",
    )
    print(analysis_response.content)


# --8<-- [end: advanced]
asyncio.run(main())
# asyncio.run(analysis())
