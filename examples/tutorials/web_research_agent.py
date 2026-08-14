import railtracks as rt

# rt.enable_logging() # uncomment for detailed logs

#### API Key Setup #####
"""
1. Create a .env file in the root of your project
2. Add the following lines to your .env file:
TAVILY_API_KEY="your_tavily_api_key_here"
OPENAI_API_KEY="your_openai_api_key_here"
"""

##### Toolset Definition #####
# Defaults: Tavily for search, httpx + trafilatura for fetch.
web = rt.prebuilt.WebSearchToolSet()

##### Agent Definitions #####
# Two-agent handoff (find the source, then answer from it) instead of one
# agent given unrestricted tool access — a clearer demo of defined control
# flow, and a template for building your own multi-step research flows.
Researcher = rt.agent_node(
    name="Researcher",
    tool_nodes=web.tool_set(),
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message=web.prompt(),
)

Summarizer = rt.agent_node(
    name="Summarizer",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message=(
        "Answer the user's question using only the provided source material. "
        "Cite the URL your answer came from."
    ),
)


##### Define the Agentic Architecture #####
@rt.function_node
async def research(question: str) -> str:
    """Flow entry to search the web, read the best source, and answer a question.

    Args:
        question (str): The question to research and answer.
    Returns:
        str: An answer grounded in fetched web content, with a source URL.
    """

    # Researcher decides what to search for, and reads the most promising result.
    findings = await rt.call(
        Researcher, f"Find and read the best source to answer: {question}"
    )

    # Summarizer turns the raw findings into a direct, cited answer.
    answer = await rt.call(
        Summarizer, f"Question: {question}\n\nSource material:\n{findings.text}"
    )
    return answer.text


#### Flow Definition #####
research_flow = rt.Flow(
    name="Web Research Flow", entry_point=research
)  # `research` function as the entry point of the flow

if __name__ == "__main__":
    question = "What is railtracks (the Python agent framework)?"
    result = research_flow.invoke(question)
    print(result)
