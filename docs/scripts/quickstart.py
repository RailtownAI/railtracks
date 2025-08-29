# --8<-- [start: setup]
import asyncio
import railtracks as rt

#########################################################################
# Define the tools you would like your agent to use                    #
# Any python function can be used as a tool as long as it has:         #
# - Type hints for input parameters                                    #
# - Google docstrings format                                           #
#########################################################################

# Make sure to include the decorator to convert your function into an `RT Tool`.
@rt.function_node
def number_of_characters(text: str, character_of_interest: str) -> int:
    """
    Count the number of occurrences of a specific character in a text.

    Args:
        text (str): The input text.
        character_of_interest (str): The character to count.

    Returns:
        int: The number of occurrences of the character in the text.
    """
    return text.count(character_of_interest)


#####################
# Create your agent #
#####################

TextAnalyzer = rt.agent_node(
    tool_nodes=[number_of_characters],
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message=(
        "You are a text analyzer. You will be given a text and return the number of characters, "
        "the number of words, and the number of occurrences of a specific character."
    ),
)
# --8<-- [end: setup]

# --8<-- [start: async_main]
async def main():
    result = await rt.call(
        TextAnalyzer,
        "How many vowels are in Tyrannosaurus?"
    )
    return result

result = asyncio.run(main())
# --8<-- [end: async_main]
print(result)