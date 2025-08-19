# --8<-- [start: setup]
import railtracks as rt

#########################################################################
# Define the tools you would like your agent to use                    #
# Any python function can be used as a tool as long as it has:         #
# - Type hints for input parameters                                    #
# - Google docstrings format                                           #
#########################################################################

def number_of_chars(text: str) -> int:
    """
    Count the number of characters in a text.

    Args:
        text (str): The input text.

    Returns:
        int: The number of characters in the text.
    """
    return len(text)

def number_of_words(text: str) -> int:
    """
    Count the number of words in a text.

    Args:
        text (str): The input text.

    Returns:
        int: The number of words in the text.
    """
    return len(text.split())

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

##################################################################
# Convert your functions into function nodes usable by the agent #
##################################################################

TotalNumberChars = rt.function_node(number_of_chars)
TotalNumberWords = rt.function_node(number_of_words)
CharacterCount = rt.function_node(number_of_characters)


#####################
# Create your agent #
#####################

TextAnalyzer = rt.agent_node(
    tool_nodes=[TotalNumberChars, TotalNumberWords, CharacterCount],
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message=(
        "You are a text analyzer. You will be given a text and return the number of characters, "
        "the number of words, and the number of occurrences of a specific character."
    ),
)
# --8<-- [end: setup]


# --8<-- [start: synchronous_call]
result = rt.call_sync(
    TextAnalyzer,
    "How many vowels are in Tyrannosaurus?"
)
# --8<-- [end: synchronous_call]

# --8<-- [start: async_main]
async def main():
    result = await rt.call(
        TextAnalyzer,
        "How many vowels are in Tyrannosaurus?"
    )
# --8<-- [end: async_main]
print(result)