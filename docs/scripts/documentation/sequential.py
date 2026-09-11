# --8<-- [start: sequential]
import railtracks as rt

llm = rt.llm.OpenAILLM("gpt-4o")

Researcher = rt.agent_node(
    name="Researcher",
    system_message="Collect the key facts about the topic the user gives you. Answer in bullet points.",
    llm=llm,
)

Writer = rt.agent_node(
    name="Writer",
    system_message="Turn the notes you are given into a single tight paragraph.",
    llm=llm,
)


@rt.function_node
async def research_then_write(topic: str) -> str:
    """Research a topic, then write the findings up as a paragraph.

    Args:
        topic: The subject to research.

    Returns:
        A one paragraph write-up of the topic.
    """
    notes = await rt.call(Researcher, topic)
    write_up = await rt.call(Writer, notes.text)
    return write_up.text


flow = rt.Flow(name="Research then Write", entry_point=research_then_write)
result = flow.invoke("How do heat pumps work?")
# --8<-- [end: sequential]
print(result)
