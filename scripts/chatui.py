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

@rt.function_node
async def chat():
    response = await rt.interactive.local_chat(ChatAgent)

interactive_flow = rt.Flow(
    name="Interactive Flow",
    entry_point=chat,
)

interactive_flow.invoke()

# --8<-- [end: interactive]

# --8<-- [start: advanced]
AnalysisAgent = rt.agent_node(
    name="AnalysisAgent",
    system_message="You are a helpful assistant that analyzes customer interactions with agents",
    llm=rt.llm.OpenAILLM("gpt-5"),
)

@rt.function_node
async def analysis():
    response = await rt.interactive.local_chat(ChatAgent)

    analysis_response = await rt.call(
        AnalysisAgent,
        f"Analyze the following conversation and provide a summary in less than 10 words:\n\n{response.message_history}",
    )

analysis_flow = rt.Flow(
    name="Analysis Flow",
    entry_point=analysis,
)

analysis_flow.invoke()
# --8<-- [end: advanced]

